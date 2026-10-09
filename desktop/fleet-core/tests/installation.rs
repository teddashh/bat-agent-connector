use bat_fleet_core::{
    discovery::Backend,
    installation::{canonical_local, Entry, Snapshot},
};
use serde_json::json;
use std::{
    ffi::OsString,
    path::{Path, PathBuf},
};

struct Fixture(PathBuf);
impl Fixture {
    fn new() -> Self {
        let path = std::env::temp_dir().join(format!(
            "bac-installation-{}-{:032x}",
            std::process::id(),
            rand::random::<u128>()
        ));
        std::fs::create_dir_all(path.join("kit/client")).unwrap();
        std::fs::write(
            path.join("kit/client/fleet-desktop.ps1"),
            b"# synthetic facade",
        )
        .unwrap();
        let value = Self(path);
        value.write(json!({"kit_root": value.0.join("kit")}));
        value
    }
    fn path(&self) -> PathBuf {
        self.0.join("fleet.json")
    }
    fn write(&self, value: serde_json::Value) {
        std::fs::write(self.path(), serde_json::to_vec(&value).unwrap()).unwrap();
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

#[test]
fn legacy_config_binds_actual_client_root_and_explicit_backend_changes_invalidate_snapshot() {
    let f = Fixture::new();
    let old = Snapshot::load(&f.path()).unwrap();
    assert_eq!(old.backend(), Backend::Powershell);
    assert_eq!(
        old.client_root(),
        canonical_local(&f.0.join("kit/client")).unwrap()
    );
    assert_eq!(old.script().parent(), Some(old.client_root()));
    let original = std::fs::read(f.path()).unwrap();
    old.verify_current().unwrap();
    assert_eq!(std::fs::read(f.path()).unwrap(), original);
    f.write(json!({"kit_root": f.0.join("kit"), "backend":"rust"}));
    assert_eq!(old.verify_current(), Err("INSTALLATION_CHANGED"));
    let new = Snapshot::load(&f.path()).unwrap();
    assert_eq!(new.backend(), Backend::Rust);
    new.verify_current().unwrap();
}

#[test]
fn unknown_keys_duplicate_keys_unknown_backend_and_unbounded_config_refuse() {
    let f = Fixture::new();
    for extra in [
        json!({"backend":"other"}),
        json!({"backend":null}),
        json!({"shell":"anything"}),
        json!({"kit_root":"relative"}),
    ] {
        let mut value = json!({"kit_root":f.0.join("kit")});
        for (key, field) in extra.as_object().unwrap() {
            value[key] = field.clone();
        }
        f.write(value);
        assert!(Snapshot::load(&f.path()).is_err());
    }
    std::fs::write(f.path(), br#"{"kit_root":"a","kit_root":"b"}"#).unwrap();
    assert!(Snapshot::load(&f.path()).is_err());
    std::fs::write(f.path(), vec![b' '; 16385]).unwrap();
    assert!(matches!(
        Snapshot::load(&f.path()),
        Err("INSTALLATION_TOO_LARGE")
    ));
}

#[test]
fn migration_payload_changes_only_backend_and_retains_installation_identity() {
    let f = Fixture::new();
    let snapshot = Snapshot::load(&f.path()).unwrap();
    let original = std::fs::read(f.path()).unwrap();
    let next = snapshot.backend_payload(Backend::Rust).unwrap();
    snapshot.validate_payload(&next, Backend::Rust).unwrap();
    assert!(snapshot
        .validate_payload(&next, Backend::Powershell)
        .is_err());
    std::fs::write(f.path(), &next).unwrap();
    assert_eq!(snapshot.verify_current(), Err("INSTALLATION_CHANGED"));
    snapshot
        .validate_payload(&original, Backend::Powershell)
        .unwrap();
    snapshot.validate_payload(&next, Backend::Rust).unwrap();
    let mut different: serde_json::Value = serde_json::from_slice(&next).unwrap();
    different["kit_root"] = json!(f.0.join("kit/client"));
    assert!(snapshot
        .validate_payload(&serde_json::to_vec(&different).unwrap(), Backend::Rust)
        .is_err());
    std::fs::rename(
        f.0.join("kit/client/fleet-desktop.ps1"),
        f.0.join("kit/client/changed.ps1"),
    )
    .unwrap();
    assert!(snapshot.validate_payload(&next, Backend::Rust).is_err());
}

#[test]
fn missing_or_replaced_required_installation_paths_refuse() {
    let f = Fixture::new();
    let snapshot = Snapshot::load(&f.path()).unwrap();
    std::fs::remove_file(f.0.join("kit/client/fleet-desktop.ps1")).unwrap();
    assert_eq!(snapshot.verify_current(), Err("INSTALLATION_CHANGED"));
    assert!(Snapshot::load(&f.path()).is_err());
    std::fs::create_dir(f.0.join("kit/client/fleet-desktop.ps1")).unwrap();
    assert_eq!(snapshot.verify_current(), Err("INSTALLATION_CHANGED"));
    assert!(Snapshot::load(&f.path()).is_err());
}

#[cfg(unix)]
#[test]
fn linked_config_or_outside_client_script_never_authorizes_local_effects() {
    use std::os::unix::fs::symlink;
    let f = Fixture::new();
    std::fs::rename(f.path(), f.0.join("source.json")).unwrap();
    symlink(f.0.join("source.json"), f.path()).unwrap();
    assert!(Snapshot::load(&f.path()).is_err());
    std::fs::remove_file(f.path()).unwrap();
    std::fs::rename(f.0.join("source.json"), f.path()).unwrap();
    let script = f.0.join("kit/client/fleet-desktop.ps1");
    std::fs::rename(&script, f.0.join("other.ps1")).unwrap();
    symlink(f.0.join("other.ps1"), &script).unwrap();
    assert!(Snapshot::load(&f.path()).is_err());
}

#[test]
fn fixed_native_entry_arguments_do_not_accept_shell_urls_extra_flags_or_relative_config() {
    let f = Fixture::new();
    assert_eq!(Entry::parse(&[]), Ok(Entry::Dashboard));
    for (flag, expected) in [
        ("--fleet-login", Entry::Login(f.path())),
        ("--fleet-supervisor", Entry::Supervisor(f.path())),
    ] {
        let args = vec![
            OsString::from(flag),
            "--fleet-config".into(),
            f.path().into_os_string(),
        ];
        assert_eq!(Entry::parse(&args), Ok(expected));
        let mut extra = args.clone();
        extra.push("--command".into());
        assert!(Entry::parse(&extra).is_err());
    }
    for args in [
        vec!["--fleet-supervisor"],
        vec!["--fleet-supervisor", "--fleet-config", "relative.json"],
        vec!["--fleet-login", "--url", "https://example.com"],
        vec!["--command", "--fleet-config", "/tmp/fleet.json"],
    ] {
        assert!(Entry::parse(&args.iter().map(OsString::from).collect::<Vec<_>>()).is_err());
    }
    assert!(canonical_local(Path::new("relative")).is_err());
}
