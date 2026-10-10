// Fixture-only UIA client. Compile once with the Windows .NET Framework compiler.
// A dedicated MTA process owns no windows; the parent enforces its 8-second deadline.
using System;
using System.Diagnostics;
using System.Globalization;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Windows.Automation;

internal static class ManagedViewProbe
{
    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr window, out uint process);

    private static void Phase(string phase)
    {
        Console.Error.WriteLine(phase);
        Console.Error.Flush();
    }

    [MTAThread]
    private static int Main(string[] args)
    {
        Phase("started");
        try
        {
            if (args.Length != 2) return 2;
            IntPtr window = new IntPtr(long.Parse(args[0], CultureInfo.InvariantCulture));
            uint expected = uint.Parse(args[1], CultureInfo.InvariantCulture);
            uint owner;
            if (GetWindowThreadProcessId(window, out owner) == 0 || owner != expected) return 2;
            Phase("owner_verified");
            ReadView(window);
            return 0;
        }
        catch (Exception)
        {
            // Never log provider exceptions, UI names, or text-entry values.
            Phase("failed");
            return 2;
        }
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static void ReadView(IntPtr window)
    {
        Phase("assemblies_loaded");
        AutomationElement root = AutomationElement.FromHandle(window);
        Phase("window_resolved");
        CacheRequest cache = new CacheRequest();
        cache.TreeScope = TreeScope.Element;
        cache.AutomationElementMode = AutomationElementMode.None;
        cache.Add(AutomationElement.ControlTypeProperty);
        cache.Add(AutomationElement.NameProperty);
        cache.Add(AutomationElement.IsEnabledProperty);
        // One owned-window query retrieves only document, text and button nodes.
        // Cached properties avoid repeated cross-process calls for every label.
        Condition wanted = new OrCondition(
            new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Document),
            new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Text),
            new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Button));
        AutomationElementCollection nodes;
        Phase("query_started");
        using (cache.Activate()) nodes = root.FindAll(TreeScope.Descendants, wanted);
        Phase("query_completed");
        bool webContent = false, authenticated = false, setup = false;
        bool configurationLoaded = false, saveEnabled = false;
        bool bounded = nodes.Count <= 2000;
        Stopwatch clock = Stopwatch.StartNew();
        for (int index = 0; bounded && index < nodes.Count; index++)
        {
            if (clock.ElapsedMilliseconds >= 2000) { bounded = false; break; }
            AutomationElement.AutomationElementInformation node = nodes[index].Cached;
            if (node.ControlType == ControlType.Document) { webContent = true; continue; }
            string label = node.Name;
            if (label == "Connected to your local Connector" || label == "已連線至本機 Connector") authenticated = true;
            if (label == "Get ready to work" || label == "準備開始工作") setup = true;
            if (label == "Configured: 0 hosts, 0 repositories" || label == "已設定 0 台主機、0 個儲存庫") configurationLoaded = true;
            if (node.ControlType == ControlType.Button && node.IsEnabled &&
                (label == "Verify and save host" || label == "驗證並儲存主機")) saveEnabled = true;
        }
        Console.WriteLine("{\"webContent\":" + Bit(webContent) + ",\"authenticated\":" + Bit(authenticated)
            + ",\"setup\":" + Bit(setup) + ",\"configurationLoaded\":" + Bit(configurationLoaded)
            + ",\"saveEnabled\":" + Bit(saveEnabled) + ",\"bounded\":" + Bit(bounded) + "}");
        Console.Out.Flush();
        Phase("completed");
    }

    private static string Bit(bool value) { return value ? "true" : "false"; }
}
