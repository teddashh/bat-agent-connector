//! Narrow local journal/config/startup file operations; never a WebView file API.
use crate::Result;
use std::{
    fs::OpenOptions,
    io::{Read, Write},
    path::Path,
};
pub(crate) const MAX_SLOT: usize = 1_048_576;
pub(crate) const MAX_JOURNAL: usize = 6_000_000;
pub(crate) fn directory(path: &Path) -> Result<()> {
    match std::fs::symlink_metadata(path) {
        Ok(m) => {
            if !m.is_dir() || m.file_type().is_symlink() {
                return Err("MIGRATION_INVALID_PATH");
            }
            #[cfg(windows)]
            {
                use std::os::windows::fs::MetadataExt;
                if m.file_attributes() & 0x400 != 0 {
                    return Err("MIGRATION_INVALID_PATH");
                }
            }
            Ok(())
        }
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(_) => Err("MIGRATION_UNREADABLE"),
    }
}
pub(crate) fn read(path: &Path, limit: usize) -> Result<Option<Vec<u8>>> {
    match std::fs::symlink_metadata(path) {
        Ok(m) if !m.is_file() || m.file_type().is_symlink() => {
            return Err("MIGRATION_INVALID_FILE")
        }
        Ok(_) => (),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(_) => return Err("MIGRATION_UNREADABLE"),
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
        options.custom_flags(0x00200000);
    }
    let file = options.open(path).map_err(|_| "MIGRATION_UNREADABLE")?;
    let metadata = file.metadata().map_err(|_| "MIGRATION_UNREADABLE")?;
    if !metadata.is_file() {
        return Err("MIGRATION_INVALID_FILE");
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        if metadata.file_attributes() & 0x400 != 0 {
            return Err("MIGRATION_INVALID_FILE");
        }
    }
    let mut bytes = Vec::new();
    file.take(limit as u64 + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| "MIGRATION_UNREADABLE")?;
    if bytes.len() > limit {
        return Err("MIGRATION_TOO_LARGE");
    }
    Ok(Some(bytes))
}
pub(crate) fn replace(
    path: &Path,
    expected: Option<&[u8]>,
    next: Option<&[u8]>,
    limit: usize,
) -> Result<()> {
    if next.is_some_and(|b| b.len() > limit) {
        return Err("MIGRATION_TOO_LARGE");
    }
    if read(path, limit)?.as_deref() != expected {
        return Err("MIGRATION_CHANGED");
    }
    if next == expected {
        return Ok(());
    }
    let Some(next) = next else {
        std::fs::remove_file(path).map_err(|_| "MIGRATION_UNAVAILABLE")?;
        return Ok(());
    };
    let parent = path.parent().ok_or("MIGRATION_INVALID_PATH")?;
    let temp = parent.join(format!(
        ".fleet-migration-{:032x}.tmp",
        rand::random::<u128>()
    ));
    let mut opts = OpenOptions::new();
    opts.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        opts.mode(0o600);
    }
    let mut file = opts.open(&temp).map_err(|_| "MIGRATION_UNAVAILABLE")?;
    let result = (|| {
        file.write_all(next).map_err(|_| "MIGRATION_UNAVAILABLE")?;
        file.sync_all().map_err(|_| "MIGRATION_UNAVAILABLE")?;
        if read(path, limit)?.as_deref() != expected {
            return Err("MIGRATION_CHANGED");
        }
        drop(file);
        std::fs::rename(&temp, path).map_err(|_| "MIGRATION_UNAVAILABLE")?;
        #[cfg(unix)]
        std::fs::File::open(parent)
            .and_then(|f| f.sync_all())
            .map_err(|_| "MIGRATION_UNAVAILABLE")?;
        Ok(())
    })();
    if result.is_err() {
        let _ = std::fs::remove_file(temp);
    }
    result
}
