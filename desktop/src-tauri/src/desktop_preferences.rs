#![cfg_attr(not(any(windows, test)), allow(dead_code))]
//! Fixed current-user login-picker preference, independent from Fleet connections/windows.
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    fs::OpenOptions,
    io::{Read, Write},
    path::Path,
};
#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Document {
    version: u8,
    show_picker: bool,
}
#[derive(Serialize)]
pub struct Snapshot {
    pub show_picker: bool,
    pub revision: String,
}
fn read(path: &Path) -> Result<Option<Vec<u8>>, String> {
    let meta = match path.symlink_metadata() {
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(_) => return Err("LOGIN_PREFERENCES_UNAVAILABLE".into()),
        Ok(v) => v,
    };
    if !meta.is_file() || meta.file_type().is_symlink() || meta.len() > 4096 {
        return Err("LOGIN_PREFERENCES_INVALID".into());
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        if meta.file_attributes() & 0x400 != 0 {
            return Err("LOGIN_PREFERENCES_INVALID".into());
        }
    }
    let mut options = OpenOptions::new();
    options.read(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK);
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        options.custom_flags(0x0020_0000);
    }
    let file = options
        .open(path)
        .map_err(|_| "LOGIN_PREFERENCES_UNAVAILABLE")?;
    let meta = file
        .metadata()
        .map_err(|_| "LOGIN_PREFERENCES_UNAVAILABLE")?;
    if !meta.is_file() || meta.len() > 4096 {
        return Err("LOGIN_PREFERENCES_INVALID".into());
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        if meta.file_attributes() & 0x400 != 0 {
            return Err("LOGIN_PREFERENCES_INVALID".into());
        }
    }
    let mut bytes = vec![];
    file.take(4097)
        .read_to_end(&mut bytes)
        .map_err(|_| "LOGIN_PREFERENCES_UNAVAILABLE")?;
    if bytes.len() > 4096 {
        return Err("LOGIN_PREFERENCES_INVALID".into());
    }
    Ok(Some(bytes))
}
fn snapshot(raw: Option<&[u8]>) -> Result<Snapshot, String> {
    let show_picker = if let Some(bytes) = raw {
        let doc: Document = serde_json::from_value(
            bat_fleet_core::strict_json::parse(bytes, 4096)
                .map_err(|_| "LOGIN_PREFERENCES_INVALID")?,
        )
        .map_err(|_| "LOGIN_PREFERENCES_INVALID")?;
        if doc.version != 1 {
            return Err("LOGIN_PREFERENCES_INVALID".into());
        }
        doc.show_picker
    } else {
        true
    };
    Ok(Snapshot {
        show_picker,
        revision: format!("{:x}", Sha256::digest(raw.unwrap_or_default())),
    })
}
pub fn load(roaming: &Path) -> Result<Snapshot, String> {
    snapshot(read(&roaming.join("bat-fleet-desktop.json"))?.as_deref())
}
/// Caller holds the shared launcher exclusion. No Startup entry or Fleet choice changes here.
pub fn save(
    roaming: &Path,
    expected: &str,
    show_picker: bool,
    mut verify: impl FnMut() -> Result<(), String>,
) -> Result<Snapshot, String> {
    let path = roaming.join("bat-fleet-desktop.json");
    let raw = read(&path)?;
    if snapshot(raw.as_deref())?.revision != expected {
        return Err("LOGIN_PREFERENCES_CHANGED".into());
    }
    verify()?;
    let bytes = serde_json::to_vec(&Document {
        version: 1,
        show_picker,
    })
    .map_err(|_| "LOGIN_PREFERENCES_INVALID")?;
    let temp = roaming.join(format!(
        "bat-fleet-desktop-{}.tmp",
        uuid::Uuid::new_v4().simple()
    ));
    let mut options = OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let result = (|| {
        let mut file = options
            .open(&temp)
            .map_err(|_| "LOGIN_PREFERENCES_UNAVAILABLE")?;
        file.write_all(&bytes)
            .and_then(|_| file.sync_all())
            .map_err(|_| "LOGIN_PREFERENCES_UNAVAILABLE")?;
        verify()?;
        if read(&path)? != raw {
            return Err("LOGIN_PREFERENCES_CHANGED".into());
        }
        drop(file);
        std::fs::rename(&temp, &path).map_err(|_| "LOGIN_PREFERENCES_UNAVAILABLE")?;
        snapshot(Some(&bytes))
    })();
    if result.is_err() {
        let _ = std::fs::remove_file(temp);
    }
    result
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn default_cancel_save_and_stale_revision_are_independent() {
        let d = tempfile::tempdir().unwrap();
        let old = load(d.path()).unwrap();
        assert!(old.show_picker);
        assert!(!d.path().join("bat-fleet-desktop.json").exists());
        let next = save(d.path(), &old.revision, false, || Ok(())).unwrap();
        assert!(!next.show_picker);
        assert!(save(d.path(), &old.revision, true, || Ok(())).is_err());
        assert!(!load(d.path()).unwrap().show_picker);
    }
    #[test]
    fn edit_during_staging_is_preserved() {
        let d = tempfile::tempdir().unwrap();
        let old = load(d.path()).unwrap();
        let mut checks = 0;
        assert!(save(d.path(), &old.revision, false, || {
            checks += 1;
            if checks == 2 {
                std::fs::write(d.path().join("bat-fleet-desktop.json"), b"edited").unwrap();
            }
            Ok(())
        })
        .is_err());
        assert_eq!(
            std::fs::read(d.path().join("bat-fleet-desktop.json")).unwrap(),
            b"edited"
        );
    }
    #[test]
    fn malformed_never_silently_selects_automatic_start() {
        let d = tempfile::tempdir().unwrap();
        for bytes in [
            b"null".as_slice(),
            br#"{"version":1,"show_picker":false,"extra":true}"#,
            br#"{"version":1,"show_picker":true,"show_picker":false}"#,
        ] {
            std::fs::write(d.path().join("bat-fleet-desktop.json"), bytes).unwrap();
            assert!(load(d.path()).is_err());
        }
    }
}
