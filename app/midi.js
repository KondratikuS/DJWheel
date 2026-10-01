/* ───────── ЖИВАЯ ДЕКА: Web MIDI ─────────
   Джог крутит колесо, касание/остановка джога — выбор, пады — семплы, одна кнопка — START / НАЗАД.
   Знакомая дека (KNOWN) работает сразу. Незнакомая — при первом же сообщении открывается мастер:
   читаем колесо (один оборот по часовой), потом пады и кнопку. Профиль хранится в localStorage
   по имени порта. Вручную мастер открывается клавишей M или пятью быстрыми тапами в левом верхнем углу.
   Работает в Chrome / Edge (ПК, Android) по https или localhost; в Safari и на iOS Web MIDI нет. */
const MIDI = (() => {
  const KEY = 'djw-midi-profiles-v1';
  const PAD_NAMES = ['KICK', 'HAT', 'CLAP', 'SNARE'];
  // коды левого дека DDJ-FLX6 — из маппинга Mixxx (7200 тиков на оборот, значение − 64)
  const flx6Jog = { enc: 'offset', sign: 1, deg: 0.05 };
  const KNOWN = [
    { match: /DDJ-FLX6/i, title: 'Pioneer DDJ-FLX6',
      profile: { jog: { 'b0:21': flx6Jog, 'b0:22': flx6Jog, 'b0:23': flx6Jog }, touch: null,
                 pads: ['97:00', '97:01', '97:02', '97:03'], action: '90:0b' } },
  ];
  // idleMs — без датчика касания столько тишины = «отпустил»; minMove° — меньше не считается (случайный толчок);
  // spinVel (градусов за кадр) и spinMove° — рулетка только от настоящего раскрута, быстрый поворот к секции её не включает
  const CFG = { idleMs: 1000, minMove: 3, spinVel: 30, spinMove: 150 };

  let access = null, profiles = {}, wiz = null;
  try { profiles = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) {}
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(profiles)); } catch (e) {} };
  const hex = b => b.toString(16).padStart(2, '0');
  const profileOf = name => profiles[name] || (KNOWN.find(k => k.match.test(name)) || {}).profile || null;

  // сообщение → {key, on, val}; Note Off и Note On с нулём сводим к одному ключу
  function parse(d) {
    let st = d[0], v = d[2] || 0; const type = st & 0xf0;
    if (type === 0x80) { st = 0x90 | (st & 0x0f); v = 0; }
    if (type !== 0x90 && type !== 0x80 && type !== 0xb0) return null;
    return { key: hex(st) + ':' + hex(d[1]), cc: type === 0xb0, val: v, on: v > 0 };
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
  function action() {
    if (state === 'start') { btn.click(); setTimeout(soundHint, 400); }
    else if (state === 'result' && back.classList.contains('show')) showStart();
  }

  function onMessage(port, data) {
    const m = parse(data); if (!m) return;
    if (wiz) return wiz.feed(port, m);
    const p = profileOf(port.name);
    if (!p) { if (m.on) { openWizard(port.name); if (wiz) wiz.feed(port, m); } return; }   // незнакомая дека подала голос — знакомимся (первое сообщение тоже в зачёт: это часто касание диска)
    const j = p.jog[m.key];
    if (j && m.cc) return turn(decode(j, m.val, absState[port.name + m.key] || (absState[port.name + m.key] = {})) * j.deg);
    if (m.key === p.touch) return touch(m.on);
    if (!m.on) return;
    const i = p.pads.indexOf(m.key); if (i >= 0) return pad(i);
    if (m.key === p.action) action();
  }

  /* ── мастер знакомства ── */
  const css = `#midiWiz{position:absolute;inset:0;z-index:30;background:rgba(6,7,9,.93);display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:6%;gap:1.1em;font-size:calc(var(--h)*.03)}
#midiWiz h2{margin:0;font-size:1.7em;letter-spacing:.04em}#midiWiz .dev{font-family:'Share Tech Mono',monospace;color:#6f86b8;letter-spacing:.15em;font-size:.8em}
#midiWiz .step{color:#2fd85a;font-family:'Share Tech Mono',monospace;letter-spacing:.2em;font-size:.8em}#midiWiz .ask{font-size:1.25em;max-width:28em;line-height:1.35}
#midiWiz .got{min-height:1.4em;color:#e8e14a;font-family:'Share Tech Mono',monospace;font-size:.85em}#midiWiz .row{display:flex;gap:.8em;margin-top:.6em}
#midiWiz button{font:700 .8em 'Montserrat',sans-serif;letter-spacing:.12em;padding:.7em 1.6em;border-radius:999px;border:2px solid #3d4047;background:linear-gradient(#2b2d31,#151618);color:#eee;cursor:pointer}
#midiDot{position:absolute;right:1%;bottom:1.5%;z-index:7;width:calc(var(--h)*.012);height:calc(var(--h)*.012);border-radius:50%;background:#2fd85a;box-shadow:0 0 8px #2fd85a;opacity:0;transition:opacity .4s;pointer-events:none}#midiDot.on{opacity:.8}
#soundHint{position:absolute;left:50%;bottom:4%;transform:translateX(-50%);z-index:8;padding:.6em 1.6em;border-radius:999px;background:rgba(232,225,74,.95);color:#111;font:700 calc(var(--h)*.022) 'Montserrat',sans-serif;letter-spacing:.12em;display:none;pointer-events:none}#soundHint.on{display:block}`;
  document.head.appendChild(Object.assign(document.createElement('style'), { textContent: css }));
  const dot = Object.assign(document.createElement('div'), { id: 'midiDot' }); $('#frame').appendChild(dot);

  function openWizard(name) {
    if (wiz) return;
    // открыт вручную — имени нет: привяжемся к порту, с которого придёт первый сигнал
    const el = document.createElement('div'); el.id = 'midiWiz';
    el.innerHTML = `<div class="dev"></div><div class="step"></div><h2></h2><div class="ask"></div><div class="got"></div>
      <div class="row"><button data-a="back">НАЗАД</button><button data-a="skip">ПРОПУСТИТЬ</button><button data-a="close">ЗАКРЫТЬ</button></div>`;
    $('#frame').appendChild(el);
    const q = s => el.querySelector(s);
    const p = { jog: {}, touch: null, pads: [], action: null };
    const steps = ['wheel', 'pad0', 'pad1', 'pad2', 'pad3', 'action', 'done'];
    let si = 0, cc = {}, notes = {}, timer = 0;
    const used = () => [...Object.keys(p.jog), p.touch, ...p.pads, p.action].filter(Boolean);
    function show() {
      const s = steps[si]; clearTimeout(timer); cc = {}; notes = {};
      q('.dev').textContent = name || 'жду сигнал с деки…'; q('.step').textContent = s === 'done' ? 'ГОТОВО' : `ШАГ ${si + 1} / ${steps.length - 1}`; q('.got').textContent = '';
      q('[data-a=back]').style.visibility = si ? 'visible' : 'hidden'; q('[data-a=skip]').style.display = s === 'done' ? 'none' : '';
      if (s === 'wheel') { q('h2').textContent = 'КОЛЕСО'; q('.ask').textContent = 'Положи руку на диск, сделай ровно один полный оборот по часовой стрелке и убери руку.'; }
      else if (s.startsWith('pad')) { const i = +s[3]; q('h2').textContent = 'ПАД ' + PAD_NAMES[i]; q('.ask').textContent = `Нажми кнопку на деке, которая будет играть ${PAD_NAMES[i]}.`; }
      else if (s === 'action') { q('h2').textContent = 'СТАРТ / НАЗАД'; q('.ask').textContent = 'Нажми кнопку, которой запускать опрос и возвращаться в начало (например PLAY). Можно пропустить — останется экран.'; }
      else { q('h2').textContent = 'ДЕКА ПОДКЛЮЧЕНА'; const n = Object.keys(p.jog).length;
        q('.ask').textContent = `Колесо: ${n ? 'есть' : 'нет'}${p.touch ? ', с датчиком касания' : ''}. Пады: ${p.pads.filter(Boolean).length} из 4. Кнопка: ${p.action ? 'есть' : 'нет'}.`;
        if (name) { profiles[name] = p; save(); } mark(); timer = setTimeout(close, 2500); }
    }
    const next = () => { si = Math.min(si + 1, steps.length - 1); show(); };
    function finishWheel() {
      const held = Object.values(notes).some(n => n.on && !n.off);        // рука ещё на диске — ждём, но не вечно
      if (held && !finishWheel.waited) { finishWheel.waited = 1; q('.got').textContent += '  — убери руку с диска'; timer = setTimeout(finishWheel, 4000); return; }
      finishWheel.waited = 0;
      let found = 0, info = [];
      for (const key in cc) {
        const v = cc[key]; if (v.length < 8) continue;
        // кодировка шага: вокруг 64 — «64 ± n»; у краёв 0/127 — дополнительный код; иначе абсолютная позиция
        const share = f => v.filter(f).length / v.length;
        const enc = share(x => Math.abs(x - 64) <= 24) > .85 ? 'offset' : share(x => x <= 24 || x >= 104) > .85 ? 'twos' : 'abs';
        const st = {}, sum = v.reduce((a, x) => a + decode({ enc, sign: 1 }, x, st), 0);
        if (Math.abs(sum) < 20) continue;
        p.jog[key] = { enc, sign: sum < 0 ? -1 : 1, deg: 360 / Math.abs(sum) }; found++; info.push(`${key.toUpperCase()} · ${Math.abs(sum)} тиков на оборот`);
      }
      if (!found) { q('.got').textContent = 'Вращение не распознано — попробуй ещё раз, полный оборот.'; cc = {}; return; }
      const t = Object.keys(notes).find(k => notes[k].on && notes[k].off); if (t) p.touch = t;
      q('.got').textContent = info.join('   ') + (t ? `   касание ${t.toUpperCase()}` : '   касание не найдено'); timer = setTimeout(next, 1800);
    }
    wiz = { feed(port, m) {
      if (!name) { name = port.name; q('.dev').textContent = name; }
      if (port.name !== name) return; const s = steps[si];
      if (s === 'wheel') {
        if (m.cc) { (cc[m.key] = cc[m.key] || []).push(m.val); q('.got').textContent = `${m.key.toUpperCase()} … ${Object.values(cc).reduce((a, x) => a + x.length, 0)}`; clearTimeout(timer); timer = setTimeout(finishWheel, 1200); }
        else { const n = notes[m.key] = notes[m.key] || {}; m.on ? n.on = 1 : n.off = 1;
          if (!m.on && Object.keys(cc).length) { clearTimeout(timer); timer = setTimeout(finishWheel, 300); } }   // убрал руку — оборот закончен
      } else if ((s.startsWith('pad') || s === 'action') && m.on && !used().includes(m.key)) {
        if (m.cc && m.val < 64) return;
        if (s === 'action') p.action = m.key; else p.pads[+s[3]] = m.key;
        q('.got').textContent = m.key.toUpperCase(); clearTimeout(timer); timer = setTimeout(next, 500);
      }
    } };
    function close() { clearTimeout(timer); el.remove(); wiz = null; }
    el.addEventListener('click', e => {
      const a = e.target.dataset && e.target.dataset.a; if (!a) return;
      if (a === 'close') close();
      else if (a === 'skip') { const s = steps[si]; if (s.startsWith('pad')) p.pads[+s[3]] = null; next(); }
      else if (a === 'back') { si = Math.max(0, si - 1); const s = steps[si]; if (s === 'wheel') { p.jog = {}; p.touch = null; } else if (s.startsWith('pad')) p.pads[+s[3]] = null; else if (s === 'action') p.action = null; show(); }
    });
    show();
  }

  // нажатие на деке браузер не считает жестом: звук включится после первого тапа по экрану
  const hintEl = Object.assign(document.createElement('div'), { id: 'soundHint', textContent: 'КОСНИСЬ ЭКРАНА — ВКЛЮЧИТСЯ ЗВУК' }); $('#frame').appendChild(hintEl);
  function soundHint() { hintEl.classList.toggle('on', !!ac && ac.state !== 'running'); }
  ['pointerdown', 'keydown'].forEach(t => addEventListener(t, () => { if (ac && ac.state !== 'running') ac.resume().then(soundHint); }));
  function mark() { dot.classList.toggle('on', !!access && [...access.inputs.values()].some(p => profileOf(p.name))); }
  function hook() { for (const p of access.inputs.values()) p.onmidimessage = e => onMessage(p, e.data); mark(); }
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
  return { openWizard, profiles: () => profiles, reset: () => { profiles = {}; save(); mark(); }, feed: (name, data) => onMessage({ name }, data) };
})();
