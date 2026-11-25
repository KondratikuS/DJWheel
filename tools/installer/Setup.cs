// DJ Wheel offline setup.
// 1. Unpacks the embedded DJWheel.zip (game, bridge, portable Python) into %USERPROFILE%\DJWheel,
//    keeping tools\bridge.json of an earlier install, and puts a "DJ Wheel" shortcut on the desktop.
// 2. Installs what lies in programs\ next to this exe and is not on the PC yet: Resolume Arena,
//    grandMA2 onPC, Windows MIDI Services (silently), the XDJ-XZ driver (its own window).
// 3. Turns on Arena's OSC input (7000) and webserver (8080) in its Preferences files.
// 4. Starts everything with the pad binding wizard (tools\start.cmd setup).
// Built by tools/build_installer.ps1 with the csc.exe of .NET Framework 4 every Windows has.
// Args for a check without windows: /quiet /dir=<folder> [/arenaprefs=<folder>]
using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Text;
using System.Text.RegularExpressions;
using System.Windows.Forms;
using Microsoft.Win32;

static class Setup
{
	// file mask in programs\, name for people, uninstall DisplayName that means "already there", silent args (null = own window)
	static readonly string[][] Programs = {
		new[] { "Resolume_Arena_*Installer.exe", "Resolume Arena", "^Resolume Arena", "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART" },
		new[] { "gMA2onPC_*.exe", "grandMA2 onPC", "^grandMA2 onPC", "/S" },
		new[] { "Windows.MIDI.Services*.exe", "Windows MIDI Services", "Windows MIDI Services Runtime", "/quiet /norestart" },
		new[] { "XDJ-XZ*.exe", "драйвер Pioneer XDJ-XZ", "XDJ-XZ", null },
	};
	const string Title = "DJ Wheel";

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
			string programs = Path.Combine(Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location), "programs");
			StringBuilder plan = new StringBuilder();
			string[][] todo = quiet ? new string[0][] : Pending(programs, plan);
			if (!quiet && MessageBox.Show("Установить DJ Wheel в\n" + dir + "\n\n" + (plan.Length > 0 ? "Ещё будут установлены:\n" + plan : "Resolume, grandMA2 и драйверы уже стоят или не лежат в папке programs.")
				+ "\n\nПотом установщик включит в Arena приём OSC и веб-сервер и откроет мастер привязки падов.", Title, MessageBoxButtons.OKCancel) != DialogResult.OK) return 1;
			Unpack(dir);
			if (!quiet) Shortcut(dir);
			foreach (string[] p in todo) Install(p);
			if (quiet) { if (args.Length > 0 && Array.Exists(args, a => a.StartsWith("/arenaprefs="))) ArenaPrefs(prefs); return 0; }
			while (Process.GetProcessesByName("Arena").Length > 0)
				if (MessageBox.Show("Закройте Resolume Arena: при выходе она перезаписывает свои настройки.", Title, MessageBoxButtons.RetryCancel) != DialogResult.Retry) break;
			if (Process.GetProcessesByName("Arena").Length == 0) ArenaPrefs(prefs);
			MessageBox.Show("Готово.\n\nОдин раз в grandMA2 onPC: Setup → Console → Global Settings → Telnet → Login Enabled, затем сохраните шоу. "
				+ "Без этого мост не увидит экзекьюторы и кью.\n\nСейчас запустятся Arena, grandMA2, мост и мастер привязки. "
				+ "Потом всё запускается ярлыком DJ Wheel на рабочем столе, мастер — файлом SETUP DJ Wheel в папке установки.", Title);
			Process.Start(new ProcessStartInfo(Path.Combine(dir, @"tools\start.cmd"), "setup") { WorkingDirectory = Path.Combine(dir, "tools"), UseShellExecute = true });
			return 0;
		}
		catch (Exception x)
		{
			if (!quiet) MessageBox.Show("Ошибка: " + x.Message, Title); else Console.Error.WriteLine(x);
			return 2;
		}
	}

	static void Unpack(string dir)
	{
		string keep = Path.Combine(dir, @"tools\bridge.json");   // the person's own output map survives a reinstall
		using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream("DJWheel.zip"))
		using (ZipArchive zip = new ZipArchive(s))
			foreach (ZipArchiveEntry e in zip.Entries)
			{
				string to = Path.GetFullPath(Path.Combine(dir, e.FullName));
				if (!to.StartsWith(Path.GetFullPath(dir), StringComparison.OrdinalIgnoreCase)) continue;
				if (e.Name == "") { Directory.CreateDirectory(to); continue; }
				if (string.Equals(to, keep, StringComparison.OrdinalIgnoreCase) && File.Exists(to)) continue;
				Directory.CreateDirectory(Path.GetDirectoryName(to));
				e.ExtractToFile(to, true);
			}
	}

	static void Shortcut(string dir)
	{
		string lnk = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "DJ Wheel.lnk");
		Type t = Type.GetTypeFromProgID("WScript.Shell");
		object sc = t.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, Activator.CreateInstance(t), new object[] { lnk });
		Type st = sc.GetType();
		st.InvokeMember("TargetPath", BindingFlags.SetProperty, null, sc, new object[] { Path.Combine(dir, @"tools\start.cmd") });
		st.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, sc, new object[] { Path.Combine(dir, "tools") });
		st.InvokeMember("Save", BindingFlags.InvokeMethod, null, sc, null);
	}

	// installers from programs\ whose program is not installed yet: {path, name, silent args}
	static string[][] Pending(string programs, StringBuilder plan)
	{
		var list = new System.Collections.Generic.List<string[]>();
		if (!Directory.Exists(programs)) return list.ToArray();
		foreach (string[] p in Programs)
		{
			string[] files = Directory.GetFiles(programs, p[0]);
			if (files.Length == 0 || Installed(p[2])) continue;
			Array.Sort(files);
			list.Add(new[] { files[files.Length - 1], p[1], p[3] });
			plan.Append("  • " + p[1] + "\n");
		}
		return list.ToArray();
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

	static void Install(string[] p)
	{
		ProcessStartInfo si = new ProcessStartInfo(p[0]) { UseShellExecute = true, Verb = "runas" };
		if (p[2] != null) si.Arguments = p[2];
		try
		{
			using (Process pr = Process.Start(si))
			{
				pr.WaitForExit();
				if (p[2] != null && pr.ExitCode != 0 && pr.ExitCode != 3010)   // 3010 = done, restart wanted
					MessageBox.Show(p[1] + ": установщик вернул код " + pr.ExitCode + ". Запустите его вручную из папки programs.", Title);
			}
		}
		catch (Exception x) { MessageBox.Show(p[1] + ": " + x.Message, Title); }
	}

	// OSC input 7000 (the bridge fires clips) and webserver 8080 (the wizard reads clip names); Arena must be closed
	static void ArenaPrefs(string prefs)
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
