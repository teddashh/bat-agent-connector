//! Per-user login entry for this installed executable, never a system-wide service.
//! Refuse unrelated entries rather than replacing them; disabling leaves central work running.
#[cfg(not(windows))]
use std::{fs, io::Write, path::PathBuf};

fn executable() -> Result<String, String> {
    let path = std::env::current_exe().map_err(|_| "MANAGED_LOGIN_PATH_UNAVAILABLE")?;
    let value = path.to_str().ok_or("MANAGED_LOGIN_PATH_INVALID")?;
    if !path.is_absolute() || value.contains(['\n', '\r', '"', '\0']) {
        return Err("MANAGED_LOGIN_PATH_INVALID".into());
    }
    Ok(value.into())
}

#[cfg(windows)]
fn expected() -> Result<String, String> {
    Ok(format!("\"{}\" --managed-login", executable()?))
}
#[cfg(windows)]
const NAME: &str = "BetterAgentDashboardManaged";
#[cfg(windows)]
fn key() -> Result<winreg::RegKey, String> {
    use winreg::{enums::*, RegKey};
    RegKey::predef(HKEY_CURRENT_USER)
        .create_subkey_with_flags(
            "Software\\Microsoft\\Windows\\CurrentVersion\\Run",
            KEY_READ | KEY_WRITE,
        )
        .map(|(key, _)| key)
        .map_err(|_| "MANAGED_LOGIN_REGISTRY_UNAVAILABLE".into())
}
#[cfg(windows)]
pub fn enabled() -> Result<bool, String> {
    match key()?.get_value::<String, _>(NAME) {
        Ok(value) if value == expected()? => Ok(true),
        Ok(_) => Err("MANAGED_LOGIN_ENTRY_CHANGED".into()),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(false),
        Err(_) => Err("MANAGED_LOGIN_REGISTRY_UNAVAILABLE".into()),
    }
}
#[cfg(windows)]
pub fn set_enabled(enable: bool) -> Result<(), String> {
    let active = enabled()?;
    if active == enable {
        return Ok(());
    }
    if enable {
        key()?
            .set_value(NAME, &expected()?)
            .map_err(|_| "MANAGED_LOGIN_WRITE_FAILED".into())
    } else {
        key()?
            .delete_value(NAME)
            .map_err(|_| "MANAGED_LOGIN_WRITE_FAILED".into())
    }
}

#[cfg(not(windows))]
fn entry() -> Result<(PathBuf, String), String> {
    let executable = executable()?;
    #[cfg(target_os = "macos")]
    {
        let home = std::env::var_os("HOME").ok_or("MANAGED_LOGIN_HOME_UNAVAILABLE")?;
        let escape = |value: &str| {
            value
                .replace('&', "&amp;")
                .replace('<', "&lt;")
                .replace('>', "&gt;")
                .replace('"', "&quot;")
                .replace('\'', "&apos;")
        };
        let path =
            PathBuf::from(home).join("Library/LaunchAgents/io.betteragent.dashboard.managed.plist");
        let body = format!("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n<plist version=\"1.0\"><dict><key>Label</key><string>io.betteragent.dashboard.managed</string><key>ProgramArguments</key><array><string>{}</string><string>--managed-login</string></array><key>RunAtLoad</key><true/></dict></plist>\n", escape(&executable));
        Ok((path, body))
    }
    #[cfg(not(target_os = "macos"))]
    {
        let root = std::env::var_os("XDG_CONFIG_HOME")
            .map(PathBuf::from)
            .or_else(|| std::env::var_os("HOME").map(|home| PathBuf::from(home).join(".config")))
            .ok_or("MANAGED_LOGIN_HOME_UNAVAILABLE")?;
        if !root.is_absolute() {
            return Err("MANAGED_LOGIN_PATH_INVALID".into());
        }
        // Desktop Entry Exec escaping has a separate percent field-code layer.
        let escaped = executable
            .replace('\\', "\\\\")
            .replace('`', "\\`")
            .replace('$', "\\$")
            .replace('%', "%%");
        Ok((root.join("autostart/io.betteragent.dashboard.managed.desktop"),
            format!("[Desktop Entry]\nType=Application\nName=Better Agent Dashboard\nExec=\"{escaped}\" --managed-login\nTerminal=false\nX-GNOME-Autostart-enabled=true\n")))
    }
}

#[cfg(not(windows))]
fn matches_entry(path: &std::path::Path, expected: &str) -> Result<bool, String> {
    match fs::symlink_metadata(path) {
        Ok(metadata) => {
            if !metadata.is_file() || metadata.file_type().is_symlink() || metadata.len() > 16384 {
                return Err("MANAGED_LOGIN_ENTRY_CHANGED".into());
            }
            if fs::read(path).map_err(|_| "MANAGED_LOGIN_ENTRY_UNAVAILABLE")? != expected.as_bytes()
            {
                return Err("MANAGED_LOGIN_ENTRY_CHANGED".into());
            }
            Ok(true)
        }
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(false),
        Err(_) => Err("MANAGED_LOGIN_ENTRY_UNAVAILABLE".into()),
    }
}
#[cfg(not(windows))]
pub fn enabled() -> Result<bool, String> {
    let (path, body) = entry()?;
    matches_entry(&path, &body)
}
#[cfg(not(windows))]
pub fn set_enabled(enable: bool) -> Result<(), String> {
    use std::os::unix::fs::OpenOptionsExt;
    let (path, body) = entry()?;
    let active = matches_entry(&path, &body)?;
    if active == enable {
        return Ok(());
    }
    if !enable {
        return fs::remove_file(path).map_err(|_| "MANAGED_LOGIN_WRITE_FAILED".into());
    }
    let parent = path.parent().ok_or("MANAGED_LOGIN_PATH_INVALID")?;
    fs::create_dir_all(parent).map_err(|_| "MANAGED_LOGIN_WRITE_FAILED")?;
    if fs::symlink_metadata(parent)
        .map_err(|_| "MANAGED_LOGIN_WRITE_FAILED")?
        .file_type()
        .is_symlink()
    {
        return Err("MANAGED_LOGIN_PATH_INVALID".into());
    }
    let temporary = parent.join(format!(".managed-login-{}", uuid::Uuid::new_v4()));
    let result = (|| {
        let mut file = fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .open(&temporary)
            .map_err(|_| "MANAGED_LOGIN_WRITE_FAILED")?;
        file.write_all(body.as_bytes())
            .map_err(|_| "MANAGED_LOGIN_WRITE_FAILED")?;
        file.sync_all().map_err(|_| "MANAGED_LOGIN_WRITE_FAILED")?;
        fs::hard_link(&temporary, &path).map_err(|_| "MANAGED_LOGIN_ENTRY_CHANGED")?;
        Ok(())
    })();
    let _ = fs::remove_file(temporary);
    result
}

#[cfg(test)]
mod tests {
    #[cfg(not(windows))]
    #[test]
    fn unknown_login_entry_is_not_adopted() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("login-entry");
        assert!(!super::matches_entry(&path, "owned").unwrap());
        std::fs::write(&path, "unrelated").unwrap();
        assert!(super::matches_entry(&path, "owned").is_err());
        assert!(super::matches_entry(&path, "unrelated").unwrap());
    }
}
