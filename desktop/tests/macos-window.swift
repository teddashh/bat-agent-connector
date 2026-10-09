// Native fixture helper: only the exact app bundle and PID launched by the test.
// No Accessibility permission changes, AppleScript, arbitrary keystrokes or PID kills.
import AppKit
import CoreGraphics

// Register this command-line helper with AppKit before sending application events.
// Reading window metadata alone does not initialize the sender's application context.
let fixtureApplication = NSApplication.shared
fixtureApplication.setActivationPolicy(.accessory)

let args = CommandLine.arguments
let identifier = "io.betteragent.dashboard"
func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}
if args.count == 2 && args[1] == "existing" {
    print(NSRunningApplication.runningApplications(withBundleIdentifier: identifier).count)
    exit(0)
}
guard args.count == 4, let pid = Int32(args[2]),
      let app = NSRunningApplication(processIdentifier: pid),
      app.bundleIdentifier == identifier,
      app.bundleURL?.standardizedFileURL.path == URL(fileURLWithPath: args[3]).standardizedFileURL.path
else { fail("Fixture app identity does not match") }
func state() -> String {
    "finished=\(app.isFinishedLaunching) policy=\(app.activationPolicy.rawValue) hidden=\(app.isHidden) terminated=\(app.isTerminated)"
}
switch args[1] {
case "hide":
    guard app.hide() else { fail("Native hide request refused: \(state())") }
case "quit":
    guard app.terminate() else { fail("Native Quit request refused: \(state())") }
case "inspect":
    let windows = (CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID)
        as? [[String: Any]] ?? []).filter {
            ($0[kCGWindowOwnerPID as String] as? Int32) == pid
                && ($0[kCGWindowLayer as String] as? Int) == 0
                && (($0[kCGWindowBounds as String] as? [String: Any])?["Width"] as? Double ?? 0) > 300
        }
    let value: [String: Any] = ["pid": pid, "hidden": app.isHidden,
        "finishedLaunching": app.isFinishedLaunching, "activationPolicy": app.activationPolicy.rawValue,
        "windows": windows.map { ["id": $0[kCGWindowNumber as String] ?? 0,
                                  "bounds": $0[kCGWindowBounds as String] ?? [:]] }]
    print(String(data: try JSONSerialization.data(withJSONObject: value), encoding: .utf8)!)
default: fail("Unknown fixture command")
}
