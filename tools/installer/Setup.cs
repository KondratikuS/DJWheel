// DJ Wheel offline setup.
// 1. Unpacks the embedded DJWheel.zip (game, bridge, portable Python) into %USERPROFILE%\DJWheel,
//    keeping tools\bridge.json of an earlier install, and puts a "DJ Wheel" shortcut on the desktop.
// 2. Installs what lies in programs\ next to this exe and is not on the PC yet: Resolume Arena,
//    grandMA2 onPC, Windows MIDI Services, the XDJ-XZ driver.
// 3. Turns on Arena's OSC input (7000) and webserver (8080) in its Preferences files.
// 4. Starts everything with the pad binding wizard (tools\start.cmd setup).
// Nothing happens out of sight: a window lists every step with its state and a running clock, and the
// vendors' installers show their own progress windows where they can (see Programs).
// Built by tools/build_installer.ps1 with the csc.exe of .NET Framework 4 every Windows has (C# 5).
// Args for a check without windows: /quiet /dir=<folder> [/arenaprefs=<folder>]
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

// one program from programs\: what the person sees, the installer file (null = not in the folder), its args
sealed class Prog
{
	public string Name, File, Args, Hint;
	public bool Installed;
}

static class Setup
{
	// file mask in programs\, name for people, uninstall DisplayName that means "already there",
	// args (null = the installer's full wizard), what the person sees while it runs.
	// Arena (Inno Setup) and MIDI Services (WiX) have a progress-only mode; grandMA2 (NSIS) has none between
	// the full wizard and /S, so it stays windowless and the setup window shows the clock for it.
	static readonly string[][] Programs = {
		new[] { "Resolume_Arena_*Installer.exe", "Resolume Arena", "^Resolume Arena", "/SILENT /SUPPRESSMSGBOXES /NORESTART", "идёт установка, окно установщика с полосой" },
		new[] { "gMA2onPC_*.exe", "grandMA2 onPC", "^grandMA2 onPC", "/S", "идёт установка, своего окна нет, обычно 2–5 минут" },
		new[] { "Windows.MIDI.Services*.exe", "Windows MIDI Services", "Windows MIDI Services Runtime", "/passive /norestart", "идёт установка, окно установщика с полосой" },
		new[] { "XDJ-XZ*.exe", "драйвер Pioneer XDJ-XZ", "XDJ-XZ", null, "пройдите окно установщика драйвера" },
	};
	public const string Title = "DJ Wheel";

	[STAThread]
	static int Main(string[] args)
	{
		bool quiet = false;
		string dir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "DJWheel");
		string prefs = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), @"Resolume Arena\Preferences");
		foreach (string a in args)
		{
			if (a == "/quiet") quiet = true;
			else if (a.StartsWith("/dir=")) dir = a.Substring(5);
			else if (a.StartsWith("/arenaprefs=")) prefs = a.Substring(12);
		}
		try
		{
			if (quiet)
			{
				Unpack(dir, null);
				if (Array.Exists(args, a => a.StartsWith("/arenaprefs="))) ArenaPrefs(prefs);
				return 0;
			}
			string programs = Path.Combine(Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location), "programs");
			List<Prog> progs = Scan(programs);
			StringBuilder plan = new StringBuilder();
			foreach (Prog p in progs) if (p.File != null && !p.Installed) plan.Append("  • " + p.Name + "\n");
			if (MessageBox.Show("Установить DJ Wheel в\n" + dir + "\n\n" + (plan.Length > 0 ? "Ещё будут установлены:\n" + plan : "Resolume, grandMA2 и драйверы уже стоят или не лежат в папке programs.")
				+ "\n\nПотом установщик включит в Arena приём OSC и веб-сервер и откроет мастер привязки падов.\nХод установки будет виден в окне.", Title, MessageBoxButtons.OKCancel) != DialogResult.OK) return 1;
			Application.EnableVisualStyles();
			SetupForm f = new SetupForm(dir, prefs, progs);
			Application.Run(f);
			return f.Failed ? 2 : 0;
		}
		catch (Exception x)
		{
			if (!quiet) MessageBox.Show("Ошибка: " + x.Message, Title); else Console.Error.WriteLine(x);
			return 2;
		}
	}

	// progress(done, total) is called per file; null = nobody watches
	public static void Unpack(string dir, Action<int, int> progress)
	{
		string keep = Path.Combine(dir, @"tools\bridge.json");   // the person's own output map survives a reinstall
		using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream("DJWheel.zip"))
		using (ZipArchive zip = new ZipArchive(s))
		{
			int i = 0, n = zip.Entries.Count;
			foreach (ZipArchiveEntry e in zip.Entries)
			{
				if (progress != null) progress(++i, n);
				string to = Path.GetFullPath(Path.Combine(dir, e.FullName));
				if (!to.StartsWith(Path.GetFullPath(dir), StringComparison.OrdinalIgnoreCase)) continue;
				if (e.Name == "") { Directory.CreateDirectory(to); continue; }
				if (string.Equals(to, keep, StringComparison.OrdinalIgnoreCase) && File.Exists(to)) continue;
				Directory.CreateDirectory(Path.GetDirectoryName(to));
				e.ExtractToFile(to, true);
			}
		}
	}

	public static void Shortcut(string dir)
	{
		string lnk = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "DJ Wheel.lnk");
		Type t = Type.GetTypeFromProgID("WScript.Shell");
		object sc = t.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, Activator.CreateInstance(t), new object[] { lnk });
		Type st = sc.GetType();
		st.InvokeMember("TargetPath", BindingFlags.SetProperty, null, sc, new object[] { Path.Combine(dir, @"tools\start.cmd") });
		st.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, sc, new object[] { Path.Combine(dir, "tools") });
		st.InvokeMember("Save", BindingFlags.InvokeMethod, null, sc, null);
	}

	// every known program: is its installer in programs\, is it on the PC already
	static List<Prog> Scan(string programs)
	{
		List<Prog> list = new List<Prog>();
		foreach (string[] p in Programs)
		{
			string[] files = Directory.Exists(programs) ? Directory.GetFiles(programs, p[0]) : new string[0];
			Array.Sort(files);
			list.Add(new Prog { Name = p[1], File = files.Length > 0 ? files[files.Length - 1] : null, Args = p[3], Hint = p[4], Installed = Installed(p[2]) });
		}
		return list;
	}

	static bool Installed(string pattern)
	{
		foreach (RegistryView v in new[] { RegistryView.Registry64, RegistryView.Registry32 })
			foreach (RegistryHive h in new[] { RegistryHive.LocalMachine, RegistryHive.CurrentUser })
				using (RegistryKey root = RegistryKey.OpenBaseKey(h, v).OpenSubKey(@"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"))
				{
					if (root == null) continue;
					foreach (string k in root.GetSubKeyNames())
						using (RegistryKey key = root.OpenSubKey(k))
						{
							string n = key == null ? null : key.GetValue("DisplayName") as string;
							if (n != null && Regex.IsMatch(n, pattern, RegexOptions.IgnoreCase)) return true;
						}
				}
		return false;
	}

	// runs one vendor installer and waits; throws with a text for the person when it did not work out
	public static void Install(Prog p)
	{
		ProcessStartInfo si = new ProcessStartInfo(p.File) { UseShellExecute = true, Verb = "runas" };
		if (p.Args != null) si.Arguments = p.Args;
		using (Process pr = Process.Start(si))
		{
			pr.WaitForExit();
			if (p.Args != null && pr.ExitCode != 0 && pr.ExitCode != 3010)   // 3010 = done, restart wanted
				throw new Exception("установщик вернул код " + pr.ExitCode + ", запустите его вручную из папки programs");
		}
	}

	// OSC input 7000 (the bridge fires clips) and webserver 8080 (the wizard reads clip names); Arena must be closed
	public static void ArenaPrefs(string prefs)
	{
		Directory.CreateDirectory(prefs);
		const string ver = "\t<versionInfo name=\"Resolume Arena\" majorVersion=\"7\" minorVersion=\"26\" microVersion=\"1\" revision=\"7833\"/>\n";
		string osc = Path.Combine(prefs, "osc.xml");
		if (File.Exists(osc))
			File.WriteAllText(osc, Regex.Replace(File.ReadAllText(osc), "<Input Enabled=\"\\d\" Port=\"\\d+\"", "<Input Enabled=\"1\" Port=\"7000\""));
		else
			File.WriteAllText(osc, "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<OscController>\n" + ver
				+ "\t<Input Enabled=\"1\" Port=\"7000\"/>\n\t<Output enabled=\"0\" sendBundles=\"0\" targetType=\"2\" targetPort=\"7001\" targetAddress=\"127.0.0.1\"/>\n</OscController>\n");
		string srv = Path.Combine(prefs, "server.xml");
		if (File.Exists(srv))
		{
			string s = File.ReadAllText(srv);
			s = Regex.Replace(s, "(<ServerController[^>]*?) enabled=\"\\d\"", "$1 enabled=\"1\"");
			s = Regex.Replace(s, "(<ServerController[^>]*?) port=\"\\d+\"", "$1 port=\"8080\"");
			File.WriteAllText(srv, s);
		}
		else
		{
			string web = Path.Combine(Path.GetDirectoryName(prefs), "Webserver");
			File.WriteAllText(srv, "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<ServerController name=\"ServerController\" enabled=\"1\" port=\"8080\" address=\"0.0.0.0\" root=\""
				+ web + "\">\n" + ver + "</ServerController>\n");
		}
	}
}

// The setup window: one row per step (waiting / running with a clock / done / error), a bar, and at the end
// the note about Telnet in grandMA2 with the button that starts everything. The work runs on its own thread.
sealed class SetupForm : Form
{
	readonly string dir, prefs;
	readonly List<Prog> progs;
	readonly ListView list = new ListView();
	readonly ProgressBar bar = new ProgressBar();
	readonly Label note = new Label();
	readonly Button go = new Button();
	readonly System.Windows.Forms.Timer tick = new System.Windows.Forms.Timer();
	readonly Stopwatch clock = new Stopwatch();
	ListViewItem running;      // the row whose clock is ticking
	string runningText;
	bool busy = true;
	public bool Failed;

	public SetupForm(string dir, string prefs, List<Prog> progs)
	{
		this.dir = dir; this.prefs = prefs; this.progs = progs;
		Text = Setup.Title + " — установка";
		Font = new Font("Segoe UI", 9.75f);
		ClientSize = new Size(700, 440);
		FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false;
		StartPosition = FormStartPosition.CenterScreen;

		list.SetBounds(12, 12, 676, 216);
		list.View = View.Details; list.FullRowSelect = true; list.HeaderStyle = ColumnHeaderStyle.Nonclickable;
		list.Columns.Add("Шаг", 300); list.Columns.Add("Состояние", 350);
		bar.SetBounds(12, 238, 676, 18);
		note.SetBounds(12, 266, 676, 122);
		note.Text = "Идёт установка. Windows может спросить разрешение для каждой программы — окно запроса иногда прячется за другими, смотрите на панель задач.";
		go.SetBounds(488, 396, 200, 32); go.Text = "Запустить DJ Wheel"; go.Enabled = false;
		go.Click += delegate { Launch(); Close(); };
		Controls.Add(list); Controls.Add(bar); Controls.Add(note); Controls.Add(go);

		tick.Interval = 500;
		tick.Tick += delegate
		{
			if (running == null) return;
			TimeSpan t = clock.Elapsed;
			running.SubItems[1].Text = runningText + " — " + (int)t.TotalMinutes + ":" + t.Seconds.ToString("00");
		};
		tick.Start();
		FormClosing += delegate(object s, FormClosingEventArgs e)
		{
			if (!busy) return;
			e.Cancel = true;
			MessageBox.Show(this, "Установка ещё идёт. Дождитесь, пока все шаги закончатся.", Setup.Title);
		};
		Shown += delegate
		{
			Thread t = new Thread(Work) { IsBackground = true };
			t.SetApartmentState(ApartmentState.STA);   // the shortcut is made through COM
			t.Start();
		};
	}

	ListViewItem Row(string name, string state)
	{
		ListViewItem it = new ListViewItem(new[] { name, state });
		Invoke((MethodInvoker)delegate { list.Items.Add(it); });
		return it;
	}

	// state of a row; ticking = it is the running one, the clock is appended to its text
	void Set(ListViewItem it, string state, Color color, bool ticking)
	{
		Invoke((MethodInvoker)delegate
		{
			running = null;
			it.SubItems[1].Text = state; it.ForeColor = color;
			it.EnsureVisible();
			if (ticking) { runningText = state; clock.Restart(); running = it; bar.Style = ProgressBarStyle.Marquee; }
			else { bar.Style = ProgressBarStyle.Blocks; bar.Value = 0; }
		});
	}

	bool Step(ListViewItem it, string doing, Action act)
	{
		Set(it, doing, Color.RoyalBlue, true);
		try { act(); Set(it, "готово", Color.Green, false); return true; }
		catch (Exception x) { Failed = true; Set(it, "ошибка: " + x.Message, Color.Firebrick, false); return false; }
	}

	void Work()
	{
		ListViewItem files = Row("Файлы DJ Wheel", "в очереди");
		ListViewItem link = Row("Ярлык на рабочем столе", "в очереди");
		List<ListViewItem> rows = new List<ListViewItem>();
		foreach (Prog p in progs)
			rows.Add(Row(p.Name, p.Installed ? "уже установлено" : p.File == null ? "нет в папке programs — пропущено" : "в очереди"));
		ListViewItem arena = Row("Настройки Arena: OSC 7000, веб-сервер 8080", "в очереди");

		Step(files, "распаковка в " + dir, delegate
		{
			Setup.Unpack(dir, delegate(int i, int n)
			{
				if (i % 20 == 0 || i == n) BeginInvoke((MethodInvoker)delegate { bar.Style = ProgressBarStyle.Blocks; bar.Maximum = n; bar.Value = i; });
			});
		});
		Step(link, "создаётся", delegate { Setup.Shortcut(dir); });
		for (int i = 0; i < progs.Count; i++)
		{
			Prog p = progs[i];
			if (p.Installed || p.File == null) { Set(rows[i], rows[i].SubItems[1].Text, Color.Gray, false); continue; }
			Step(rows[i], p.Hint, delegate { Setup.Install(p); });
		}

		// Arena rewrites its preferences on exit, so they are only touched while it is closed
		bool closed = true;
		while (Process.GetProcessesByName("Arena").Length > 0)
		{
			DialogResult r = DialogResult.Cancel;
			Invoke((MethodInvoker)delegate { r = MessageBox.Show(this, "Закройте Resolume Arena: при выходе она перезаписывает свои настройки.", Setup.Title, MessageBoxButtons.RetryCancel); });
			if (r != DialogResult.Retry) { closed = false; break; }
		}
		if (closed) Step(arena, "записываются", delegate { Setup.ArenaPrefs(prefs); });
		else Set(arena, "пропущено: Arena открыта. Включите вручную: Preferences → OSC и Webserver", Color.Firebrick, false);

		Invoke((MethodInvoker)delegate
		{
			busy = false;
			bar.Style = ProgressBarStyle.Blocks; bar.Maximum = 1; bar.Value = 1;
			note.Text = (Failed ? "Закончено, но не всё получилось — смотрите строки с ошибкой выше.\n\n" : "Готово.\n\n")
				+ "Один раз в grandMA2 onPC: Setup → Console → Global Settings → Telnet → Login Enabled, затем сохраните шоу. Без этого мост не увидит экзекьюторы и кью.\n\n"
				+ "Кнопка запустит Arena, grandMA2, мост и мастер привязки. Потом всё запускается ярлыком DJ Wheel на рабочем столе, мастер — файлом SETUP DJ Wheel в папке установки.";
			go.Enabled = true; go.Focus(); Activate();
		});
	}

	void Launch()
	{
		try { Process.Start(new ProcessStartInfo(Path.Combine(dir, @"tools\start.cmd"), "setup") { WorkingDirectory = Path.Combine(dir, "tools"), UseShellExecute = true }); }
		catch (Exception x) { MessageBox.Show(this, "Не запустилось: " + x.Message, Setup.Title); }
	}
}
