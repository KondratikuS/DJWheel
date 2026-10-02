/* ───────── ЖИВАЯ ДЕКА: Web MIDI ─────────
   Джог крутит колесо, касание/остановка джога — выбор, пады — семплы, одна кнопка — START / НАЗАД.
   Знакомая дека (KNOWN) работает сразу. Незнакомая — при первом же сообщении открывается мастер:
   читаем колесо (один оборот по часовой), потом пады и кнопку. Профиль хранится в localStorage
   по имени порта. Вручную мастер открывается клавишей M или пятью быстрыми тапами в левом верхнем углу.
   Работает в Chrome / Edge (ПК, Android) по https или localhost; в Safari и на iOS Web MIDI нет. */
const MIDI = (() => {
  const KEY = 'djw-midi-profiles-v1';
  const PAD_NAMES = ['KICK', 'HAT', 'CLAP', 'SNARE', 'TOM', 'CRASH', 'HORN', 'LASER'];
  // коды левого дека DDJ-FLX6 — из маппинга Mixxx (7200 тиков на оборот, значение − 64)
  const flx6Jog = { enc: 'offset', sign: 1, deg: 0.05 };
  const KNOWN = [
    { match: /DDJ-FLX6/i, title: 'Pioneer DDJ-FLX6',
      profile: { jog: { 'b0:21': flx6Jog, 'b0:22': flx6Jog, 'b0:23': flx6Jog }, touch: null,
                 pads: ['97:00', '97:01', '97:02', '97:03', '97:04', '97:05', '97:06', '97:07'], play: '90:0b', cue: '90:0c', fader: { key: 'b6:1f', min: 0, max: 127 } } },
  ];
  // idleMs — без датчика касания столько тишины = «отпустил»; minMove° — меньше не считается (случайный толчок);
  // spinVel (градусов за кадр) и spinMove° — рулетка только от настоящего раскрута, быстрый поворот к секции её не включает
  const CFG = { idleMs: 1000, minMove: 3, spinVel: 30, spinMove: 150 };
  const TURNS = 3;           // в мастере крутим несколько оборотов и берём среднее: ровно 360° рукой не сделать

  let access = null, profiles = {}, wiz = null;
  try { profiles = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) {}
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(profiles)); } catch (e) {} };
  const hex = b => b.toString(16).padStart(2, '0');
  // у одной деки бывает несколько портов («XDJ-XZ (1)», «XDJ-XZ (2)») — профиль общий, по имени без номера
  // а адреса на разных портах могут совпадать, поэтому ключ сообщения несёт номер порта: «2/b4:0b»
  const base = n => String(n).replace(/\s*\(\d+\)\s*$/, '');
  const tagOf = n => (String(n).match(/\((\d+)\)\s*$/) || [])[1] || '';
  const split = key => { const i = key.indexOf('/'); return i < 0 ? ['', key] : [key.slice(0, i), key.slice(i + 1)]; };
  // профили первых версий хранились по имени порта и без номера в ключах — переносим
  for (const k of Object.keys(profiles)) {
    const b = base(k), t = tagOf(k); if (b === k) continue;
    const o = profiles[k], T = x => (x && t && !x.includes('/') ? t + '/' + x : x); delete profiles[k]; if (profiles[b]) continue;
    profiles[b] = { jog: Object.fromEntries(Object.entries(o.jog || {}).map(([x, v]) => [T(x), v])), touch: T(o.touch) || null, pads: (o.pads || []).map(T),
                    play: T(o.play || o.action) || null, cue: T(o.cue) || null, fader: o.fader ? { ...o.fader, key: T(o.fader.key) } : null };
  }
  const profileOf = name => profiles[name] || (KNOWN.find(k => k.match.test(name)) || {}).profile || null;

  // сообщение → {key, on, val}; Note Off и Note On с нулём сводим к одному ключу
  function parse(d, tag) {
    let st = d[0], v = d[2] || 0; const type = st & 0xf0;
    if (type === 0x80) { st = 0x90 | (st & 0x0f); v = 0; }
    if (type !== 0x90 && type !== 0x80 && type !== 0xb0) return null;
    return { key: (tag ? tag + '/' : '') + hex(st) + ':' + hex(d[1]), cc: type === 0xb0, val: v, on: v > 0 };
  }
  const decode = (j, v, st) => {
    if (j.enc === 'offset') return (v - 64) * j.sign;
    if (j.enc === 'twos') return (v < 64 ? v : v - 128) * j.sign;
    const prev = st.prev; st.prev = v; if (prev == null) return 0;          // абсолютная позиция с переходом через 0
    let dd = v - prev; if (dd > 64) dd -= 128; if (dd < -64) dd += 128; return dd * j.sign;
  };

  /* ── колесо ── */
  let g = null, idle = 0, touching = false; const absState = {};
  function turn(deg) {
    if (state !== 'question' || locked || !deg) return;
    const now = performance.now();
    if (!g) { g = { moved: 0, win: 0, t: now }; cancelAnimationFrame(raf); platter.style.transition = 'none'; platter.classList.add('grab'); }
    setRot(clamp(rot + deg)); highlight(); g.moved += Math.abs(deg);
    // скорость окнами по 50 мс, в тех же единицах, что у пальца: градусы за кадр
    if (now - g.t > 50) { const v = g.win / (now - g.t) * 16; g.win = 0; g.t = now;
      if (Math.abs(v) >= CFG.spinVel && g.moved > CFG.spinMove) { end(); return roulette(); } }
    g.win += deg;
    clearTimeout(idle); idle = setTimeout(release, touching ? DATA.dwellMs : CFG.idleMs);
  }
  function end() { clearTimeout(idle); platter.classList.remove('grab'); g = null; }
  function release() {
    if (!g) return; const moved = g.moved; end();
    if (state === 'question' && !locked) moved >= CFG.minMove ? settle() : snapTo(nearest());
  }
  function touch(on) { touching = on; if (!on) release(); else if (g) { clearTimeout(idle); idle = setTimeout(release, DATA.dwellMs); } }

  /* ── пады и кнопка ── */
  function pad(i) {
    if (state !== 'result') return;
    const b = $$('.pad')[i]; if (!b) return;
    playSample(b.dataset.s); b.classList.add('hit'); setTimeout(() => b.classList.remove('hit'), 120);
  }
  // PLAY — старт, CUE — назад на финале; если CUE не привязан, назад делает PLAY
  function play(p) {
    if (state === 'start') { btn.click(); setTimeout(soundHint, 400); }
    else if (!p.cue) cue();
  }
  function cue() { if (state === 'result' && back.classList.contains('show')) showStart(); }

  // диагностика (клавиша D): что пришло и что игра с этим сделала
  let dbg = null;
  function why(port, data, m, p) {
    if (!m) return 'не нота и не CC — пропуск';
    if (wiz) return 'идёт в мастер';
    if (!p) return 'для этого порта нет профиля';
    if (p.jog[m.key] && m.cc) return state !== 'question' ? `колесо, но сейчас «${state}» — крутится только на вопросах` : locked ? 'колесо, но ответ уже выбран (пауза)' : 'колесо';
    if (m.key === p.touch) return 'касание ' + (m.on ? 'вкл' : 'выкл');
    if (p.fader && m.key === p.fader.key) return 'фейдер микса';
    const i = p.pads.indexOf(m.key); if (i >= 0) return `пад ${PAD_NAMES[i]}` + (state !== 'result' ? ' (играет только на финале)' : '');
    if (m.key === (p.play || p.action)) return 'PLAY'; if (m.key === p.cue) return 'CUE';
    return 'не привязано ни к чему';
  }
  function debug(port, data, m, p) {
    const h = [...data].map(b => hex(b).toUpperCase()).join(' '), ins = access ? [...access.inputs.values()].map(x => x.name).join(', ') : 'нет доступа к MIDI';
    const pr = p ? `колесо ${Object.keys(p.jog).join(',') || '—'} · касание ${p.touch || '—'} · падов ${p.pads.filter(Boolean).length} · play ${p.play || p.action || '—'} · cue ${p.cue || '—'} · фейдер ${p.fader ? p.fader.key : '—'}` : '—';
    dbg.textContent = `порты: ${ins}
последнее: ${port.full || port.name} · ${h} → ${why(port, data, m, p)}
профиль: ${pr}
состояние: ${state}`;
  }
  addEventListener('keydown', e => {
    if (!/^[dDвВ]$/.test(e.key)) return;
    if (dbg) { dbg.remove(); dbg = null; return; }
    dbg = Object.assign(document.createElement('pre'), { id: 'midiDbg', textContent: 'жду сообщение с деки…' }); $('#frame').appendChild(dbg);
  });

  function onMessage(port, data) {
    const m = parse(data, port.tag);
    if (dbg) debug(port, data, m, m && profileOf(port.name));
    if (!m) return;
    if (wiz) return wiz.feed(port, m);
    const p = profileOf(port.name);
    if (!p) { if (m.on) { openWizard(port.name); if (wiz) wiz.feed(port, m); } return; }   // незнакомая дека подала голос — знакомимся (первое сообщение тоже в зачёт: это часто касание диска)
    let j = p.jog[m.key];
    if (!j && sibling(p, m, port.name)) { j = p.jog[m.key]; keep(port, p); }
    if (j && m.cc) { if (cand) cand.ticks++; return turn(decode(j, m.val, absState[port.name + m.key] || (absState[port.name + m.key] = {})) * j.deg); }
    if (m.key === p.touch) return touch(m.on);
    if (p.fader && m.cc && m.key === p.fader.key) { setMix((m.val - p.fader.min) / Math.max(1, p.fader.max - p.fader.min)); return showMix(); }
    const i = p.pads.indexOf(m.key); if (i >= 0) { if (m.on) pad(i); return; }
    if (m.key === (p.play || p.action)) { if (m.on) play(p); return; }          // action — поле из первых профилей
    if (m.key === p.cue) { if (m.on) cue(); return; }
    if (learnTouch(p, m)) { keep(port, p); touch(false); }
  }

  /* У джога один энкодер, но несколько «голосов»: обод, верх с касанием, верх без vinyl — это соседние CC на том же канале.
     Откалибровали один (например, крутили за обод) — остальные признаём сами и даём им те же параметры.
     Чтобы не принять за колесо соседний регулятор, смотрим первые шесть значений: у энкодера это мелкие шаги. */
  const pend = {}, rejected = {}; let cand = null;
  function sibling(p, m, tag) {
    if (!m.cc || p.jog[m.key] || rejected[tag + m.key] || (p.fader && p.fader.key === m.key)) return null;
    const [mt, mk] = split(m.key);                                         // тот же порт, тот же канал, соседний номер
    const k = Object.keys(p.jog).find(k => { const [t, x] = split(k); return p.jog[k].enc !== 'abs' && t === mt && x.slice(0, 2) === mk.slice(0, 2) && Math.abs(parseInt(x.slice(3), 16) - parseInt(mk.slice(3), 16)) <= 3; });
    if (!k) return null;
    const v = pend[tag + m.key] = pend[tag + m.key] || []; v.push(m.val); if (v.length < 6) return null;
    delete pend[tag + m.key];
    const small = p.jog[k].enc === 'offset' ? v.every(x => Math.abs(x - 64) <= 24) : v.every(x => x <= 24 || x >= 104);
    if (!small) { rejected[tag + m.key] = 1; return null; }
    return p.jog[m.key] = { ...p.jog[k] };
  }
  // касание не привязано: нота, которая началась до вращения и кончилась после него, — это датчик касания
  function learnTouch(p, m) {
    if (p.touch || m.cc) return false;
    if (m.on) { cand = { key: m.key, ticks: 0 }; return false; }
    const ok = cand && cand.key === m.key && cand.ticks >= 3; cand = null;
    if (ok) p.touch = m.key; return ok;
  }
  const keep = (port, p) => { if (profiles[port.name] === p) save(); };

  /* ── мастер знакомства ── */
  const css = `#midiWiz{position:absolute;inset:0;z-index:30;background:rgba(6,7,9,.93);display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:6%;gap:1.1em;font-size:calc(var(--h)*.03)}
#midiWiz h2{margin:0;font-size:1.7em;letter-spacing:.04em}#midiWiz .dev{font-family:'Share Tech Mono',monospace;color:#6f86b8;letter-spacing:.15em;font-size:.8em}
#midiWiz .step{color:#2fd85a;font-family:'Share Tech Mono',monospace;letter-spacing:.2em;font-size:.8em}#midiWiz .ask{font-size:1.25em;max-width:28em;line-height:1.35}
#midiWiz .got{min-height:1.4em;color:#e8e14a;font-family:'Share Tech Mono',monospace;font-size:.85em}#midiWiz .row{display:flex;gap:.8em;margin-top:.6em}
#midiWiz button{font:700 .8em 'Montserrat',sans-serif;letter-spacing:.12em;padding:.7em 1.6em;border-radius:999px;border:2px solid #3d4047;background:linear-gradient(#2b2d31,#151618);color:#eee;cursor:pointer}
#midiDot{position:absolute;right:1%;bottom:1.5%;z-index:7;width:calc(var(--h)*.012);height:calc(var(--h)*.012);border-radius:50%;background:#2fd85a;box-shadow:0 0 8px #2fd85a;opacity:0;transition:opacity .4s;pointer-events:none}#midiDot.on{opacity:.8}
#mixBar{position:absolute;left:50%;top:14.2%;transform:translateX(-50%);z-index:8;width:24%;display:flex;align-items:center;gap:.8em;color:#d9e6ff;font:700 calc(var(--h)*.02) 'Share Tech Mono',monospace;opacity:0;transition:opacity .3s;pointer-events:none}#mixBar.on{opacity:1}
#mixBar i{flex:1;height:calc(var(--h)*.008);border-radius:99px;background:#2b2d31;position:relative;box-shadow:0 0 0 1px #000}#mixBar b{position:absolute;top:50%;width:calc(var(--h)*.03);height:calc(var(--h)*.03);margin:calc(var(--h)*-.015) 0 0 calc(var(--h)*-.015);border-radius:50%;background:#e8e8ea;box-shadow:0 0 10px rgba(255,255,255,.6)}
#midiDbg{position:absolute;left:1%;top:15%;z-index:40;margin:0;padding:.6em .9em;max-width:62%;white-space:pre-wrap;background:rgba(0,0,0,.82);border:1px solid #3d4047;border-radius:8px;color:#e8e14a;font:calc(var(--h)*.018)/1.5 'Share Tech Mono',monospace;pointer-events:none}
#soundHint{position:absolute;left:50%;bottom:4%;transform:translateX(-50%);z-index:8;padding:.6em 1.6em;border-radius:999px;background:rgba(232,225,74,.95);color:#111;font:700 calc(var(--h)*.022) 'Montserrat',sans-serif;letter-spacing:.12em;display:none;pointer-events:none}#soundHint.on{display:block}`;
  document.head.appendChild(Object.assign(document.createElement('style'), { textContent: css }));
  const dot = Object.assign(document.createElement('div'), { id: 'midiDot' }); $('#frame').appendChild(dot);

  function openWizard(name) {
    if (wiz) return;
    // открыт вручную — имени нет: привяжемся к порту, с которого придёт первый сигнал
    const el = document.createElement('div'); el.id = 'midiWiz';
    el.innerHTML = `<div class="dev"></div><div class="step"></div><h2></h2><div class="ask"></div><div class="got"></div>
      <div class="row tune"><button data-a="less">− МЕДЛЕННЕЕ</button><button data-a="more">БЫСТРЕЕ +</button></div>
      <div class="row"><button data-a="back">НАЗАД</button><button data-a="skip">ПРОПУСТИТЬ</button><button data-a="close">ЗАКРЫТЬ</button></div>`;
    $('#frame').appendChild(el);
    const q = s => el.querySelector(s);
    const p = { jog: {}, touch: null, pads: [], play: null, cue: null, fader: null }; let had = false;
    const steps = ['wheel', 'check', 'pad0', 'pad1', 'pad2', 'pad3', 'pad4', 'pad5', 'pad6', 'pad7', 'play', 'cue', 'fader', 'done'];
    let si = 0, cc = {}, notes = {}, timer = 0, acc = 0, accT = 0; const chk = {};
    const used = () => [...Object.keys(p.jog), p.touch, ...p.pads, p.play, p.cue, p.fader && p.fader.key].filter(Boolean);
    function show() {
      const s = steps[si]; clearTimeout(timer); cc = {}; notes = {};
      q('.dev').textContent = name || 'жду сигнал с деки…'; q('.step').textContent = s === 'done' ? 'ГОТОВО' : `ШАГ ${si + 1} / ${steps.length - 1}`; q('.got').textContent = '';
      const now = s === 'wheel' ? Object.keys(p.jog).join(', ') : s.startsWith('pad') ? p.pads[+s[3]] : s === 'play' || s === 'cue' ? p[s] : s === 'fader' ? p.fader && p.fader.key : '';
      if (had && now) q('.got').textContent = `сейчас: ${now.toUpperCase()} — «Пропустить» оставит как есть`;
      q('[data-a=back]').style.visibility = si ? 'visible' : 'hidden'; q('[data-a=skip]').style.display = s === 'done' ? 'none' : '';
      q('[data-a=skip]').textContent = s === 'check' ? 'ДАЛЬШЕ' : 'ПРОПУСТИТЬ'; q('.tune').style.display = s === 'check' ? '' : 'none';
      if (s === 'wheel') { q('h2').textContent = 'КОЛЕСО'; q('.ask').textContent = `Положи руку на диск сверху, сделай ${TURNS} полных оборота по часовой стрелке и убери руку. Точность не нужна — возьмём среднее.`; }
      else if (s === 'check') { acc = 0; q('h2').textContent = 'ПРОВЕРКА'; q('.ask').textContent = 'Поверни диск на четверть оборота — сначала взявшись за верх, потом за обод. Здесь должно быть около 90°. Если заметно больше или меньше, поправь кнопками.'; q('.got').textContent = '0°';
        if (!Object.keys(p.jog).length) return next(); }
      else if (s.startsWith('pad')) { const i = +s[3]; q('h2').textContent = 'ПАД ' + PAD_NAMES[i]; q('.ask').textContent = `Нажми кнопку на деке, которая будет играть ${PAD_NAMES[i]}.`; }
      else if (s === 'play') { q('h2').textContent = 'КНОПКА PLAY'; q('.ask').textContent = 'Нажми PLAY на деке — этой кнопкой запускается опрос.'; }
      else if (s === 'cue') { q('h2').textContent = 'КНОПКА CUE'; q('.ask').textContent = 'Нажми CUE на деке — этой кнопкой на финале возвращаемся в начало. Если пропустить, назад будет делать PLAY.'; }
      else if (s === 'fader') { q('h2').textContent = 'ФЕЙДЕР МИКСА'; q('.ask').textContent = 'Проведи фейдер микса от края до края — на финале он переливает один трек в другой. Потом «Дальше».'; q('[data-a=skip]').textContent = 'ДАЛЬШЕ'; }
      else { q('h2').textContent = 'ДЕКА ПОДКЛЮЧЕНА'; const n = Object.keys(p.jog).length;
        q('.ask').textContent = `Колесо: ${n ? 'есть' : 'нет'}${p.touch ? ', с датчиком касания' : ''}. Пады: ${p.pads.filter(Boolean).length} из 8. PLAY: ${p.play ? 'есть' : 'нет'}. CUE: ${p.cue ? 'есть' : 'нет'}. Фейдер: ${p.fader ? 'есть' : 'нет'}.`;
        if (name) { profiles[name] = p; save(); } mark(); timer = setTimeout(close, 2500); }
    }
    const next = () => { si = Math.min(si + 1, steps.length - 1); show(); };
    // у деки уже есть профиль — берём его за основу, чтобы можно было перепривязать одну вещь, а остальное пропустить
    function adopt() { const ex = name && profileOf(name); if (!ex) return; const c = JSON.parse(JSON.stringify(ex));
      Object.assign(p, { jog: c.jog || {}, touch: c.touch || null, pads: c.pads || [], play: c.play || c.action || null, cue: c.cue || null, fader: c.fader || null }); had = true; show(); }
    const note = t => { if (!q('.ask').textContent.includes(t)) q('.ask').textContent += ` (${t})`; };
    function finishWheel() {
      const held = Object.values(notes).some(n => n.on && !n.off);        // рука ещё на диске — ждём, но не вечно
      if (held && !finishWheel.waited) { finishWheel.waited = 1; q('.got').textContent += '  — убери руку с диска'; timer = setTimeout(finishWheel, 4000); return; }
      finishWheel.waited = 0;
      let found = 0, info = []; const jogNew = {};
      for (const key in cc) {
        const v = cc[key]; if (v.length < 8) continue;
        // кодировка шага: пробуем все три («64 ± n», дополнительный код, абсолютная позиция). Оборот в одну
        // сторону должен давать шаги одного знака; из таких берём ту, где самые мелкие шаги мельче: на медленных
        // участках настоящая кодировка даёт ±1..3, а ошибочная — числа около 60
        let best = null;
        for (const enc of ['offset', 'twos', 'abs']) {
          if (enc === 'abs' && !v.some((x, i) => i && Math.abs(x - v[i - 1]) > 64)) continue;   // ход без перехода через ноль — это фейдер или ручка, а не колесо
          const st = {}, d = v.map(x => decode({ enc, sign: 1 }, x, st)), sum = d.reduce((a, x) => a + x, 0), abs = d.reduce((a, x) => a + Math.abs(x), 0);
          if (abs < 24 || Math.abs(sum) / abs < .9) continue;
          const mags = d.map(Math.abs).filter(Boolean).sort((x, y) => x - y), low = mags[Math.floor(mags.length * .1)] || 0;
          if (!best || low < best.low) best = { enc, sum, low };
        }
        if (!best) continue;
        const { enc, sum } = best;
        jogNew[key] = { enc, sign: sum < 0 ? -1 : 1, deg: 360 * TURNS / Math.abs(sum) }; found++; info.push(`${key.toUpperCase()} · около ${Math.round(Math.abs(sum) / TURNS)} тиков на оборот`);
      }
      if (!found) { q('.got').textContent = 'Это не похоже на колесо (фейдер или ручка?) — покрути сам диск, в одну сторону.'; cc = {}; notes = {}; return; }
      p.jog = jogNew; p.touch = null;                                     // новая калибровка заменяет старую целиком
      const t = Object.keys(notes).find(k => notes[k].both); if (t) p.touch = t;
      q('.got').textContent = info.join('   ') + (t ? `   касание ${t.toUpperCase()}` : '   касание не найдено'); timer = setTimeout(next, 1800);
    }
    wiz = { feed(port, m) {
      if (!name) { name = port.name; q('.dev').textContent = name; adopt(); }
      if (port.name !== name) return; const s = steps[si];
      if (s === 'wheel') {
        if (m.cc) { (cc[m.key] = cc[m.key] || []).push(m.val); q('.got').textContent = `${m.key.toUpperCase()} … ${Object.values(cc).reduce((a, x) => a + x.length, 0)}`; clearTimeout(timer); timer = setTimeout(finishWheel, 2000); }
        else { const n = notes[m.key] = notes[m.key] || {}; if (m.on) { n.on = 1; n.off = 0; n.seenOn = 1; } else { n.off = 1; if (n.seenOn) n.both = 1; } }   // руку между оборотами перехватывают — шаг закрывает только тишина
      } else if (s === 'check') {
        if (sibling(p, m, 'wiz')) note('второй канал колеса добавлен');
        if (learnTouch(p, m)) note('датчик касания найден');
        const j = p.jog[m.key]; if (m.key === p.touch && m.on) acc = 0;
        if (j && m.cc) { if (cand) cand.ticks++; const now = performance.now(); if (!p.touch && now - accT > 1500) acc = 0; accT = now; acc += decode(j, m.val, chk) * j.deg; q('.got').textContent = Math.round(acc) + '°'; }
      } else if (s === 'fader') {                       // берём CC с самым широким ходом
        if (!m.cc) return; const r = cc[m.key] = cc[m.key] || { min: 127, max: 0, prev: m.val };
        if (Math.abs(m.val - r.prev) > 64) r.wrap = 1; r.prev = m.val;          // скачок через ноль — это энкодер, не фейдер
        r.min = Math.min(r.min, m.val); r.max = Math.max(r.max, m.val);
        const best = Object.keys(cc).filter(k => !cc[k].wrap).sort((a, b) => (cc[b].max - cc[b].min) - (cc[a].max - cc[a].min))[0];
        const ok = best && cc[best].max - cc[best].min >= 40;
        if (ok) { p.fader = { key: best, min: cc[best].min, max: cc[best].max }; delete p.jog[best]; }   // если его раньше ошибочно записали колесом — убираем оттуда
        q('.got').textContent = `${m.key.toUpperCase()} · ${m.val}` + (ok ? `   ход ${p.fader.min}…${p.fader.max}` : '   веди до конца');
      } else if ((s.startsWith('pad') || s === 'play' || s === 'cue') && m.on && (!used().includes(m.key) || m.key === (s.startsWith('pad') ? p.pads[+s[3]] : p[s]))) {
        if (m.cc && m.val < 64) return;
        if (s === 'play' || s === 'cue') p[s] = m.key; else p.pads[+s[3]] = m.key;
        q('.got').textContent = m.key.toUpperCase(); clearTimeout(timer); timer = setTimeout(next, 500);
      }
    } };
    function close() { clearTimeout(timer); el.remove(); wiz = null; }
    el.addEventListener('click', e => {
      const a = e.target.dataset && e.target.dataset.a; if (!a) return;
      if (a === 'close') { if (name && (Object.keys(p.jog).length || p.pads.some(Boolean) || p.play || p.cue || p.fader)) { profiles[name] = p; save(); mark(); } close(); }
      else if (a === 'skip') next();                                       // пропуск ничего не стирает
      else if (a === 'less' || a === 'more') { const k = a === 'more' ? 1.1 : 1 / 1.1; for (const key in p.jog) p.jog[key].deg *= k; acc *= k; q('.got').textContent = Math.round(acc) + '°'; }
      else if (a === 'back') { si = Math.max(0, si - 1); const s = steps[si]; if (s === 'wheel') { p.jog = {}; p.touch = null; } else if (s.startsWith('pad')) p.pads[+s[3]] = null; else if (s === 'play' || s === 'cue') p[s] = null; else if (s === 'fader') p.fader = null; show(); }
    });
    show();
  }

  // полоска микса: появляется на пару секунд, когда двигают фейдер
  const mixEl = Object.assign(document.createElement('div'), { id: 'mixBar', innerHTML: '<span>A</span><i><b></b></i><span>B</span>' }); $('#frame').appendChild(mixEl); let mixT = 0;
  function showMix() { mixEl.querySelector('b').style.left = mix * 100 + '%'; mixEl.classList.add('on'); clearTimeout(mixT); mixT = setTimeout(() => mixEl.classList.remove('on'), 1800); }
  // нажатие на деке браузер не считает жестом: звук включится после первого тапа по экрану
  const hintEl = Object.assign(document.createElement('div'), { id: 'soundHint', textContent: 'КОСНИСЬ ЭКРАНА — ВКЛЮЧИТСЯ ЗВУК' }); $('#frame').appendChild(hintEl);
  function soundHint() { hintEl.classList.toggle('on', !!ac && ac.state !== 'running'); }
  ['pointerdown', 'keydown'].forEach(t => addEventListener(t, () => { if (ac && ac.state !== 'running') ac.resume().then(soundHint); }));
  function mark() { dot.classList.toggle('on', !!access && [...access.inputs.values()].some(p => profileOf(base(p.name)))); }
  function hook() { for (const p of access.inputs.values()) p.onmidimessage = e => onMessage({ name: base(p.name), tag: tagOf(p.name), full: p.name }, e.data); mark(); }
  async function init() {
    if (!navigator.requestMIDIAccess) return;
    try { access = await navigator.requestMIDIAccess(); } catch (e) { return; }
    hook(); access.onstatechange = hook;
  }
  // мастер вручную: клавиша M или пять быстрых тапов в левом верхнем углу
  addEventListener('keydown', e => { if ((e.key === 'm' || e.key === 'M' || e.key === 'ь' || e.key === 'Ь') && !wiz) openWizard(); });
  let taps = [];
  addEventListener('pointerdown', e => {
    const f = $('#frame').getBoundingClientRect();
    if (e.clientX - f.left > f.width * .08 || e.clientY - f.top > f.height * .12) return;
    const now = performance.now(); taps = taps.filter(t => now - t < 2000); taps.push(now);
    if (taps.length >= 5) { taps = []; openWizard(); }
  });
  init();
  // feed — подать сообщение вручную (отладка без железа): MIDI.feed('имя порта', [0xB0, 0x22, 0x41])
  return { openWizard, profiles: () => profiles, reset: () => { profiles = {}; save(); mark(); }, feed: (name, data) => onMessage({ name: base(name), tag: tagOf(name), full: name }, data) };
})();
