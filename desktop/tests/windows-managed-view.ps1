# Bounded UI Automation probe, launched by the owned installed-app fixture.
# Only fixed-label booleans leave this process; never read text-entry values.
param([Parameter(Mandatory)][long]$WindowHandle, [Parameter(Mandatory)][int]$OwnerProcess)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class ManagedViewWindow {
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr window, out uint process);
}
'@
$owner = [uint32]0
$null = [ManagedViewWindow]::GetWindowThreadProcessId([IntPtr]$WindowHandle, [ref]$owner)
if ($owner -ne $OwnerProcess) { throw 'Owned fixture window identity changed' }
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$state = [ordered]@{webContent=$false; authenticated=$false; setup=$false; configurationLoaded=$false; saveEnabled=$false; bounded=$true}
$pending = [Collections.Generic.Stack[System.Windows.Automation.AutomationElement]]::new()
$pending.Push([System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$WindowHandle))
$walker = [System.Windows.Automation.TreeWalker]::RawViewWalker
$clock = [Diagnostics.Stopwatch]::StartNew()
$visited = 0
while ($pending.Count -gt 0) {
    if (++$visited -gt 2000 -or $clock.ElapsedMilliseconds -ge 2000) { $state.bounded = $false; break }
    $node = $pending.Pop()
    $current = $node.Current
    if ($current.ControlType -eq [System.Windows.Automation.ControlType]::Document) { $state.webContent = $true }
    if ($current.ControlType -eq [System.Windows.Automation.ControlType]::Text -or
        $current.ControlType -eq [System.Windows.Automation.ControlType]::Button) {
        $label = $current.Name
        if ($label -cin @('Connected to your local Connector', '已連線至本機 Connector')) { $state.authenticated = $true }
        if ($label -cin @('Get ready to work', '準備開始工作')) { $state.setup = $true }
        if ($label -cin @('Configured: 0 hosts, 0 repositories', '已設定 0 台主機、0 個儲存庫')) { $state.configurationLoaded = $true }
        if ($current.ControlType -eq [System.Windows.Automation.ControlType]::Button -and $current.IsEnabled -and
            $label -cin @('Verify and save host', '驗證並儲存主機')) { $state.saveEnabled = $true }
    }
    $child = $walker.GetFirstChild($node)
    while ($null -ne $child) {
        if ($pending.Count + $visited -ge 2000 -or $clock.ElapsedMilliseconds -ge 2000) { $state.bounded = $false; break }
        $pending.Push($child)
        $child = $walker.GetNextSibling($child)
    }
    if (-not $state.bounded) { break }
}
$state | ConvertTo-Json -Compress
