#![cfg(windows)]
use bat_fleet_core::{discovery::Backend, windows_startup::Codec};
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
$sc=$ws.CreateShortcut((Join-Path $r 'fixture.lnk'))
$sc.TargetPath=Join-Path $r 'system\wscript.exe'
$vbs=Join-Path $r 'kit\client\Open BAT.vbs'
$extra=$env:BAT_FLEET_STARTUP_EXTRA
if ($extra -eq 'case') {$vbs=$vbs.ToUpperInvariant();$extra=''}
$sc.Arguments='"'+$vbs+'"'+$extra
$sc.WorkingDirectory=Join-Path $r 'kit\client'
$sc.Description='Synthetic Kit startup, never executed'
$sc.Save()
"#,
    )
    .unwrap();
    let exe = PathBuf::from(std::env::var_os("SystemRoot").unwrap())
        .join("System32/WindowsPowerShell/v1.0/powershell.exe");
    for extra in ["", "case", " --unexpected"] {
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
                .env("BAT_FLEET_STARTUP_FIXTURE", &t.0)
                .env("BAT_FLEET_STARTUP_EXTRA", extra)
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .spawn()
                .unwrap(),
        );
        let until = Instant::now() + Duration::from_secs(30);
        loop {
            if let Some(status) = child.0.try_wait().unwrap() {
                assert!(status.success());
                break;
            }
            assert!(Instant::now() < until);
            std::thread::sleep(Duration::from_millis(20));
        }
        let bytes = std::fs::read(t.0.join("fixture.lnk")).unwrap();
        if extra.is_empty() || extra == "case" {
            assert_eq!(c.classify(&bytes), Ok(Backend::Powershell));
        } else {
            assert!(c.classify(&bytes).is_err());
        }
    }
}
