#![cfg(windows)]
use bat_fleet_core::{discovery::Backend, installation::canonical_local, windows_startup::Codec};
use std::{
    path::PathBuf,
    process::{Child, Command, Stdio},
    time::{Duration, Instant},
};
struct Temp(PathBuf);
impl Temp {
    fn new() -> Self {
        let p = std::env::temp_dir().join(format!(
            "bac-startup-{}-{:032x}",
            std::process::id(),
            rand::random::<u128>()
        ));
        for d in ["kit/client", "app", "system", "other"] {
            std::fs::create_dir_all(p.join(d)).unwrap();
        }
        for f in [
            "kit/client/Open BAT.vbs",
            "app/dashboard.exe",
            "system/wscript.exe",
            "fleet.json",
            "other/foreign.exe",
        ] {
            std::fs::write(p.join(f), b"synthetic file, never executed").unwrap();
        }
        Self(p)
    }
    fn codec(&self) -> Codec {
        Codec::new(
            &self.0.join("kit/client"),
            &self.0.join("app/dashboard.exe"),
            &self.0.join("fleet.json"),
            &self.0.join("system"),
        )
        .unwrap()
    }
}
impl Drop for Temp {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}
#[test]
fn temporary_links_round_trip_exact_fixed_commands_and_reject_foreign_sources() {
    let t = Temp::new();
    let c = t.codec();
    for backend in [Backend::Powershell, Backend::Rust] {
        let b = c.render(backend).unwrap();
        assert_eq!(c.classify(&b), Ok(backend));
        let mut elevated = b.clone();
        let flags = u32::from_le_bytes(elevated[20..24].try_into().unwrap()) | 0x2000;
        elevated[20..24].copy_from_slice(&flags.to_le_bytes());
        assert_eq!(c.classify(&elevated), Err("STARTUP_UNOWNED"));
        let other = Temp::new();
        assert!(other.codec().classify(&b).is_err());
    }
    for b in [vec![], vec![0; 64], vec![0; 1_048_577]] {
        assert!(c.classify(&b).is_err());
    }
}
#[test]
fn real_wscript_shell_shortcut_uses_kit_format_but_modified_arguments_refuse() {
    use std::os::windows::ffi::{OsStrExt, OsStringExt};
    use windows_sys::Win32::Storage::FileSystem::GetShortPathNameW;
    struct Owned(Child);
    impl Drop for Owned {
        fn drop(&mut self) {
            let _ = self.0.kill();
            let _ = self.0.wait();
        }
    }
    let t = Temp::new();
    let c = t.codec();
    // Read-only relative to the installed system: all shortcuts/targets live in this temp fixture.
    let script = t.0.join("write-fixture.ps1");
    std::fs::write(
        &script,
        br#"$ErrorActionPreference='Stop'
$r=$env:BAT_FLEET_STARTUP_FIXTURE
$ws=New-Object -ComObject WScript.Shell
$link=Join-Path $r 'fixture.lnk'
$sc=$ws.CreateShortcut($link)
$case=$env:BAT_FLEET_STARTUP_CASE
if ($env:BAT_FLEET_STARTUP_BACKEND -eq 'powershell') {
    $sc.TargetPath=Join-Path $r 'system\wscript.exe'
    $argument=Join-Path $r 'kit\client\Open BAT.vbs'
    $working=Join-Path $r 'kit\client'
    if ($case -eq 'reparse') {
        $alias=Join-Path $r 'client-alias'
        if (-not (Test-Path $alias)) {New-Item -ItemType Junction -Path $alias -Target $working | Out-Null}
        $working=$alias
        $argument=Join-Path $alias 'Open BAT.vbs'
    }
    $prefix=''
} else {
    $sc.TargetPath=Join-Path $r 'app\dashboard.exe'
    $argument=Join-Path $r 'fleet.json'
    $working=Join-Path $r 'app'
    $prefix='--fleet-login --fleet-config '
}
if ($case -eq 'case') {$argument=$argument.ToUpperInvariant();$working=$working.ToUpperInvariant()}
$sc.Arguments=$prefix+'"'+$argument+'"'
if ($case -eq 'extra') {$sc.Arguments+=' --unexpected'}
if ($case -eq 'foreign-target') {$sc.TargetPath=Join-Path $r 'other\foreign.exe'}
if ($case -eq 'foreign-cwd') {$working=Join-Path $r 'other'}
$sc.WorkingDirectory=$working
$sc.Description='Synthetic Kit startup, never executed'
$sc.Save()
$read=$ws.CreateShortcut($link)
$diagnostic=@{target=$read.TargetPath;arguments=$read.Arguments;working=$read.WorkingDirectory} | ConvertTo-Json -Compress
[IO.File]::WriteAllText((Join-Path $r 'fixture-diagnostic.json'),$diagnostic)
"#,
    )
    .unwrap();
    let exe = PathBuf::from(std::env::var_os("SystemRoot").unwrap())
        .join("System32/WindowsPowerShell/v1.0/powershell.exe");
    let long_root = canonical_local(&t.0).unwrap();
    let input: Vec<u16> = long_root.as_os_str().encode_wide().chain(Some(0)).collect();
    let mut output = vec![0u16; 32768];
    let count =
        unsafe { GetShortPathNameW(input.as_ptr(), output.as_mut_ptr(), output.len() as u32) }
            as usize;
    assert!(count > 0 && count < output.len());
    let short_root = PathBuf::from(std::ffi::OsString::from_wide(&output[..count]));
    for backend in [Backend::Powershell, Backend::Rust] {
        for (spelling, root) in [("long", &long_root), ("short", &short_root)] {
            for case in [
                "exact",
                "case",
                "extra",
                "foreign-target",
                "foreign-cwd",
                "reparse",
            ] {
                if backend == Backend::Rust && case == "reparse" {
                    continue; // the PS case proves directory aliases are not resolved into ownership
                }
                let mut child = Owned(
                    Command::new(&exe)
                        .args([
                            "-NoProfile",
                            "-NonInteractive",
                            "-ExecutionPolicy",
                            "Bypass",
                            "-File",
                        ])
                        .arg(&script)
                        .env("BAT_FLEET_STARTUP_FIXTURE", root)
                        .env("BAT_FLEET_STARTUP_CASE", case)
                        .env(
                            "BAT_FLEET_STARTUP_BACKEND",
                            if backend == Backend::Powershell {
                                "powershell"
                            } else {
                                "rust"
                            },
                        )
                        .stdin(Stdio::null())
                        .stdout(Stdio::null())
                        .stderr(Stdio::null())
                        .spawn()
                        .unwrap(),
                );
                let until = Instant::now() + Duration::from_secs(30);
                loop {
                    if let Some(status) = child.0.try_wait().unwrap() {
                        assert!(
                            status.success(),
                            "fixture creation failed: {backend:?}/{spelling}/{case}"
                        );
                        break;
                    }
                    assert!(Instant::now() < until);
                    std::thread::sleep(Duration::from_millis(20));
                }
                let bytes = std::fs::read(t.0.join("fixture.lnk")).unwrap();
                let actual = c.classify(&bytes);
                let expected = if matches!(case, "exact" | "case") {
                    Ok(backend)
                } else {
                    Err("STARTUP_UNOWNED")
                };
                assert_eq!(actual, expected,
                    "synthetic fixture {backend:?}/{spelling}/{case}, flags={:#x}, WScript fields={}",
                    u32::from_le_bytes(bytes[20..24].try_into().unwrap()),
                    std::fs::read_to_string(t.0.join("fixture-diagnostic.json")).unwrap());
            }
        }
    }
}
