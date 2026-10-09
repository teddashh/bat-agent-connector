//! Fixed Startup shortcut codec. Never resolves/executes a link or accepts command text.
use crate::{
    discovery::{windows_path, Backend},
    installation::{canonical_local, local_path},
    migration_io::MAX_SLOT,
    Result,
};
use std::{
    marker::PhantomData,
    path::{Path, PathBuf},
    rc::Rc,
};
use windows::{
    core::{Interface, PCWSTR},
    Win32::{System::Com::*, UI::Shell::*},
};
struct Apartment(PhantomData<Rc<()>>);
impl Apartment {
    fn new() -> Result<Self> {
        unsafe { CoInitializeEx(None, COINIT_APARTMENTTHREADED) }
            .ok()
            .map_err(|_| "STARTUP_UNAVAILABLE")?;
        Ok(Self(PhantomData))
    }
}
impl Drop for Apartment {
    fn drop(&mut self) {
        unsafe { CoUninitialize() };
    }
}
fn wide(value: &str) -> Result<Vec<u16>> {
    if value.contains('\0') || value.encode_utf16().count() > 32766 {
        return Err("STARTUP_INVALID");
    }
    Ok(value.encode_utf16().chain(Some(0)).collect())
}
fn value(buf: &[u16]) -> Result<String> {
    let n = buf.iter().position(|c| *c == 0).ok_or("STARTUP_INVALID")?;
    String::from_utf16(&buf[..n]).map_err(|_| "STARTUP_INVALID")
}
/// Only native discovery should call this; tests pass a temporary folder to migration Store.
pub fn startup_directory() -> Result<PathBuf> {
    let raw = unsafe { SHGetKnownFolderPath(&FOLDERID_Startup, KF_FLAG_DONT_VERIFY, None) }
        .map_err(|_| "STARTUP_UNAVAILABLE")?;
    let text = unsafe { raw.to_string() }.map_err(|_| "STARTUP_INVALID");
    unsafe { CoTaskMemFree(Some(raw.0.cast())) };
    let path = PathBuf::from(text?);
    if !path.is_absolute() || !local_path(&path) {
        return Err("STARTUP_INVALID");
    }
    Ok(path)
}
pub struct Codec {
    client: String,
    native: String,
    config: String,
    wscript: String,
}
impl Codec {
    /// All four paths come from trusted native installation/system discovery, not IPC.
    pub fn new(
        client: &Path,
        native: &Path,
        config: &Path,
        system_directory: &Path,
    ) -> Result<Self> {
        let client = canonical_local(client)?;
        let vbs = canonical_local(&client.join("Open BAT.vbs"))?;
        let native = canonical_local(native)?;
        let config = canonical_local(config)?;
        let system = canonical_local(system_directory)?;
        let wscript = canonical_local(&system.join("wscript.exe"))?;
        if !client.is_dir()
            || !vbs.is_file()
            || !vbs.starts_with(&client)
            || !native.is_file()
            || !config.is_file()
            || !wscript.is_file()
            || !wscript.starts_with(&system)
        {
            return Err("STARTUP_INVALID");
        }
        let text = |p: PathBuf| p.to_str().map(str::to_owned).ok_or("STARTUP_INVALID");
        Ok(Self {
            client: text(client)?,
            native: text(native)?,
            config: text(config)?,
            wscript: text(wscript)?,
        })
    }
    fn expected(&self, backend: Backend) -> (String, String, String) {
        match backend {
            Backend::Powershell => (
                self.wscript.clone(),
                format!("\"{}\\Open BAT.vbs\"", self.client),
                self.client.clone(),
            ),
            Backend::Rust => (
                self.native.clone(),
                format!("--fleet-login --fleet-config \"{}\"", self.config),
                Path::new(&self.native)
                    .parent()
                    .unwrap()
                    .to_str()
                    .unwrap()
                    .into(),
            ),
        }
    }
    fn arguments_match(&self, backend: Backend, arguments: &str) -> bool {
        let (prefix, expected) = match backend {
            Backend::Powershell => ("\"", format!("{}\\Open BAT.vbs", self.client)),
            Backend::Rust => ("--fleet-login --fleet-config \"", self.config.clone()),
        };
        arguments
            .strip_prefix(prefix)
            .and_then(|v| v.strip_suffix('"'))
            .and_then(|v| windows_path(v).ok())
            .zip(windows_path(&expected).ok())
            .is_some_and(|(a, b)| a.eq_ignore_ascii_case(&b))
    }
    fn link() -> Result<IShellLinkW> {
        unsafe { CoCreateInstance(&ShellLink, None, CLSCTX_INPROC_SERVER) }
            .map_err(|_| "STARTUP_UNAVAILABLE")
    }
    pub fn classify(&self, bytes: &[u8]) -> Result<Backend> {
        if bytes.is_empty() || bytes.len() > MAX_SLOT {
            return Err("STARTUP_INVALID");
        }
        let _apartment = Apartment::new()?;
        let link = Self::link()?;
        let stream = unsafe { SHCreateMemStream(Some(bytes)) }.ok_or("STARTUP_UNAVAILABLE")?;
        let persist: IPersistStream = link.cast().map_err(|_| "STARTUP_UNAVAILABLE")?;
        unsafe { persist.Load(&stream) }.map_err(|_| "STARTUP_INVALID")?;
        let list: IShellLinkDataList = link.cast().map_err(|_| "STARTUP_UNAVAILABLE")?;
        let flags = unsafe { list.GetFlags() }.map_err(|_| "STARTUP_INVALID")?;
        let allowed = SLDF_HAS_ID_LIST.0
            | SLDF_HAS_LINK_INFO.0
            | SLDF_HAS_NAME.0
            | SLDF_HAS_RELPATH.0
            | SLDF_HAS_WORKINGDIR.0
            | SLDF_HAS_ARGS.0
            | SLDF_HAS_ICONLOCATION.0
            | SLDF_UNICODE.0
            | SLDF_FORCE_NO_LINKINFO.0
            | SLDF_FORCE_NO_LINKTRACK.0
            | SLDF_ENABLE_TARGET_METADATA.0
            | SLDF_DISABLE_LINK_PATH_TRACKING.0
            | SLDF_DISABLE_KNOWNFOLDER_RELATIVE_TRACKING.0
            | SLDF_NO_KF_ALIAS.0
            | SLDF_NO_PIDL_ALIAS.0;
        if flags & !(allowed as u32) != 0
            || unsafe { link.GetHotkey() }.map_err(|_| "STARTUP_INVALID")? != 0
        {
            return Err("STARTUP_UNOWNED");
        }
        let mut path = vec![0; 32768];
        let mut args = vec![0; 32768];
        let mut cwd = vec![0; 32768];
        unsafe {
            link.GetPath(&mut path, std::ptr::null_mut(), SLGP_RAWPATH.0 as u32)
                .map_err(|_| "STARTUP_INVALID")?;
            link.GetArguments(&mut args)
                .map_err(|_| "STARTUP_INVALID")?;
            link.GetWorkingDirectory(&mut cwd)
                .map_err(|_| "STARTUP_INVALID")?;
        }
        let path = windows_path(&value(&path)?)?;
        let args = value(&args)?;
        let cwd = windows_path(&value(&cwd)?)?;
        for backend in [Backend::Powershell, Backend::Rust] {
            let (expected, _, working) = self.expected(backend);
            if path.eq_ignore_ascii_case(&windows_path(&expected)?)
                && self.arguments_match(backend, &args)
                && cwd.eq_ignore_ascii_case(&windows_path(&working)?)
            {
                return Ok(backend);
            }
        }
        Err("STARTUP_UNOWNED")
    }
    pub fn render(&self, backend: Backend) -> Result<Vec<u8>> {
        let _apartment = Apartment::new()?;
        let link = Self::link()?;
        let (path, args, cwd) = self.expected(backend);
        let path = wide(&path)?;
        let args = wide(&args)?;
        let cwd = wide(&cwd)?;
        unsafe {
            link.SetPath(PCWSTR(path.as_ptr()))
                .map_err(|_| "STARTUP_UNAVAILABLE")?;
            link.SetArguments(PCWSTR(args.as_ptr()))
                .map_err(|_| "STARTUP_UNAVAILABLE")?;
            link.SetWorkingDirectory(PCWSTR(cwd.as_ptr()))
                .map_err(|_| "STARTUP_UNAVAILABLE")?;
        }
        let persist: IPersistStream = link.cast().map_err(|_| "STARTUP_UNAVAILABLE")?;
        let stream = unsafe { SHCreateMemStream(None) }.ok_or("STARTUP_UNAVAILABLE")?;
        unsafe { persist.Save(&stream, true) }.map_err(|_| "STARTUP_UNAVAILABLE")?;
        let mut stat = STATSTG::default();
        unsafe { stream.Stat(&mut stat, STATFLAG_NONAME) }.map_err(|_| "STARTUP_UNAVAILABLE")?;
        if stat.cbSize == 0 || stat.cbSize > MAX_SLOT as u64 {
            return Err("STARTUP_INVALID");
        }
        unsafe { stream.Seek(0, STREAM_SEEK_SET, None) }.map_err(|_| "STARTUP_UNAVAILABLE")?;
        let mut bytes = vec![0; stat.cbSize as usize];
        let mut read = 0;
        unsafe {
            stream.Read(
                bytes.as_mut_ptr().cast(),
                bytes.len() as u32,
                Some(&mut read),
            )
        }
        .ok()
        .map_err(|_| "STARTUP_UNAVAILABLE")?;
        if read as usize != bytes.len() {
            return Err("STARTUP_INVALID");
        }
        // Same bounded codec must prove what will be written to the Startup slot.
        if self.classify(&bytes)? != backend {
            return Err("STARTUP_INVALID");
        }
        Ok(bytes)
    }
}
