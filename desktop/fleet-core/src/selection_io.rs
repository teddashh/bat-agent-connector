//! Fixed local preference storage. Call from a blocking native worker, not the WebView thread.
use crate::{
    configuration::{data_directory, Configuration},
    digest,
    selection::Preferences,
    Result,
};
use std::{
    fs::{File, OpenOptions},
    io::{Read, Write},
    path::{Path, PathBuf},
    sync::atomic::{AtomicU64, Ordering},
};

#[cfg(windows)]
use crate::windows::PreferenceLock;

#[cfg(not(windows))]
struct PreferenceLock {
    _file: File,
}
#[cfg(not(windows))]
impl PreferenceLock {
    fn acquire(path: &Path) -> Result<Self> {
        let mut name = path.as_os_str().to_owned();
        name.push(".lock");
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(Path::new(&name))
            .map_err(|_| "SELECTION_BUSY")?;
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
        loop {
            match file.try_lock() {
                Ok(()) => return Ok(Self { _file: file }),
                Err(std::fs::TryLockError::WouldBlock) if std::time::Instant::now() < deadline => {
                    std::thread::sleep(std::time::Duration::from_millis(20))
                }
                Err(_) => return Err("SELECTION_BUSY"),
            }
        }
    }
}

fn read(path: &Path) -> Result<Option<Vec<u8>>> {
    let file = match File::open(path) {
        Ok(file) => file,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(_) => return Err("SELECTION_UNREADABLE"),
    };
    if !file
        .metadata()
        .map_err(|_| "SELECTION_UNREADABLE")?
        .is_file()
    {
        return Err("SELECTION_INVALID");
    }
    let mut bytes = Vec::new();
    file.take(262145)
        .read_to_end(&mut bytes)
        .map_err(|_| "SELECTION_UNREADABLE")?;
    if bytes.len() > 262144 {
        return Err("SELECTION_INVALID");
    }
    Ok(Some(bytes))
}

pub struct Snapshot {
    preferences: Preferences,
    configuration_binding: String,
    pub revision: String,
    directory: PathBuf,
    raw: Option<Vec<u8>>,
    legacy: Option<Vec<u8>>,
}
impl Snapshot {
    pub fn preferences(&self) -> &Preferences {
        &self.preferences
    }
}
pub struct Store {
    roaming: PathBuf,
}
impl Store {
    pub fn new(roaming: PathBuf) -> Self {
        Self { roaming }
    }
    fn paths(&self) -> Result<(PathBuf, PathBuf, PathBuf)> {
        let directory = data_directory(&self.roaming)?;
        Ok((
            directory.join("fleet-client.json"),
            directory.join("open-bat-selection.json"),
            directory,
        ))
    }
    fn read_at(
        configuration: &Configuration,
        directory: &Path,
        path: &Path,
        legacy_path: &Path,
    ) -> Result<Snapshot> {
        let raw = read(path)?;
        let legacy = if raw.is_none() {
            read(legacy_path)?
        } else {
            None
        };
        let preferences =
            Preferences::load(&configuration.inventory, raw.as_deref(), legacy.as_deref())?;
        Ok(Snapshot {
            preferences,
            configuration_binding: configuration.binding().into(),
            revision: digest(raw.as_deref().unwrap_or_default()),
            directory: directory.into(),
            raw,
            legacy,
        })
    }
    pub fn read(&self, configuration: &Configuration) -> Result<Snapshot> {
        let (path, legacy, directory) = self.paths()?;
        std::fs::create_dir_all(&directory).map_err(|_| "SELECTION_UNREADABLE")?;
        let _guard = PreferenceLock::acquire(&path)?;
        configuration.verify_current()?;
        if data_directory(&self.roaming)? != directory {
            return Err("DATA_DIRECTORY_CHANGED");
        }
        let snapshot = Self::read_at(configuration, &directory, &path, &legacy)?;
        configuration.verify_current()?;
        Ok(snapshot)
    }
    /// `owner` must freshly prove the controllable monitor epoch (or positive absence),
    /// including current login ownership. Unknown evidence returns an error, never None.
    /// The original snapshot binds configuration, bytes and one-time legacy migration,
    /// beyond the PowerShell-compatible public preference revision.
    pub fn set_connections(
        &self,
        configuration: &Configuration,
        expected: &Snapshot,
        connections: &[String],
        epoch: Option<&str>,
        mut owner: impl FnMut() -> Result<Option<String>>,
    ) -> Result<Snapshot> {
        if epoch.is_some_and(|value| !crate::ownership::epoch_valid(value)) {
            return Err("INVALID_REQUEST");
        }
        if configuration.binding() != expected.configuration_binding {
            return Err("CONFIGURATION_CHANGED");
        }
        let (path, legacy, directory) = self.paths()?;
        if directory != expected.directory {
            return Err("DATA_DIRECTORY_CHANGED");
        }
        let _guard = PreferenceLock::acquire(&path)?;
        let mut check = || -> Result<()> {
            configuration.verify_current()?;
            if !configuration.issues.is_empty() {
                return Err("CONFIGURATION_INVALID");
            }
            if data_directory(&self.roaming)? != directory {
                return Err("DATA_DIRECTORY_CHANGED");
            }
            let observed = owner()?;
            if observed
                .as_deref()
                .is_some_and(|value| !crate::ownership::epoch_valid(value))
            {
                return Err("OWNER_UNPROVEN");
            }
            if observed.as_deref() != epoch {
                return Err("MONITOR_EPOCH_CHANGED");
            }
            let current = Self::read_at(configuration, &directory, &path, &legacy)?;
            if current.raw != expected.raw || current.legacy != expected.legacy {
                return Err("SELECTION_CHANGED");
            }
            configuration.verify_current()?;
            if data_directory(&self.roaming)? != directory {
                return Err("DATA_DIRECTORY_CHANGED");
            }
            Ok(())
        };
        check()?;
        let preferences = expected
            .preferences
            .set_connections(&configuration.inventory, connections)?;
        let bytes = preferences.persisted(&configuration.inventory)?;
        let (temporary, mut file) = temporary(&directory)?;
        let result = (|| {
            file.write_all(&bytes)
                .map_err(|_| "SELECTION_UNAVAILABLE")?;
            file.sync_all().map_err(|_| "SELECTION_UNAVAILABLE")?;
            check()?;
            drop(file);
            // Never delete the old preferences first. Rename replaces in one OS operation.
            std::fs::rename(&temporary, &path).map_err(|_| "SELECTION_UNAVAILABLE")?;
            Ok(Snapshot {
                preferences,
                configuration_binding: configuration.binding().into(),
                revision: digest(&bytes),
                directory: directory.clone(),
                raw: Some(bytes),
                legacy: None,
            })
        })();
        if result.is_err() {
            let _ = std::fs::remove_file(&temporary);
        }
        result
    }
}

fn temporary(directory: &Path) -> Result<(PathBuf, File)> {
    static NEXT: AtomicU64 = AtomicU64::new(0);
    for _ in 0..64 {
        let path = directory.join(format!(
            "fleet-client.{}.{}.tmp",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        match OpenOptions::new().write(true).create_new(true).open(&path) {
            Ok(file) => return Ok((path, file)),
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(_) => return Err("SELECTION_UNAVAILABLE"),
        }
    }
    Err("SELECTION_UNAVAILABLE")
}
