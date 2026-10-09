//! Fixed native profile files; no path in this module comes from IPC.
use crate::Result;
use std::{
    fs::OpenOptions,
    io::{Read, Write},
    path::Path,
};
pub(crate) const LIMIT: usize = 1024 * 1024;
fn plain(metadata: &std::fs::Metadata) -> bool {
    if metadata.file_type().is_symlink() {
        return false;
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        if metadata.file_attributes() & 0x400 != 0 {
            return false;
        }
    }
    true
}
pub(crate) fn directory(path: &Path) -> Result<()> {
    let meta = path
        .symlink_metadata()
        .map_err(|_| "PROFILE_INDEX_UNAVAILABLE")?;
    if !meta.is_dir() || !plain(&meta) {
        return Err("PROFILE_INDEX_UNPROVEN");
    }
    Ok(())
}
pub(crate) fn read(path: &Path) -> Result<Vec<u8>> {
    directory(path.parent().ok_or("PROFILE_INDEX_UNPROVEN")?)?;
    let meta = path
        .symlink_metadata()
        .map_err(|_| "PROFILE_INDEX_UNAVAILABLE")?;
    if !meta.is_file() || !plain(&meta) || meta.len() > LIMIT as u64 {
        return Err("PROFILE_INDEX_UNPROVEN");
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
        .map_err(|_| "PROFILE_INDEX_UNAVAILABLE")?;
    let meta = file.metadata().map_err(|_| "PROFILE_INDEX_UNPROVEN")?;
    if !meta.is_file() || !plain(&meta) || meta.len() > LIMIT as u64 {
        return Err("PROFILE_INDEX_UNPROVEN");
    }
    let mut bytes = Vec::new();
    file.take(LIMIT as u64 + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| "PROFILE_INDEX_UNAVAILABLE")?;
    if bytes.len() > LIMIT {
        return Err("PROFILE_INDEX_UNPROVEN");
    }
    Ok(bytes)
}
pub(crate) fn replace(
    path: &Path,
    expected: &[u8],
    bytes: &[u8],
    mut verify: impl FnMut() -> Result<()>,
) -> Result<()> {
    if bytes.len() > LIMIT {
        return Err("PROFILE_INDEX_UNPROVEN");
    }
    let dir = path.parent().ok_or("PROFILE_INDEX_UNPROVEN")?;
    verify()?;
    if read(path)? != expected {
        return Err("PROFILE_INDEX_CHANGED");
    }
    let temporary = dir.join(format!("fleet-profile-{:032x}.tmp", rand::random::<u128>()));
    let mut options = OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut file = options
        .open(&temporary)
        .map_err(|_| "PROFILE_INDEX_UNAVAILABLE")?;
    let result = (|| {
        file.write_all(bytes)
            .and_then(|_| file.sync_all())
            .map_err(|_| "PROFILE_INDEX_UNAVAILABLE")?;
        verify()?;
        if read(path)? != expected {
            return Err("PROFILE_INDEX_CHANGED");
        }
        drop(file);
        std::fs::rename(&temporary, path).map_err(|_| "PROFILE_INDEX_UNAVAILABLE")
    })();
    if result.is_err() {
        let _ = std::fs::remove_file(temporary);
    }
    result
}
