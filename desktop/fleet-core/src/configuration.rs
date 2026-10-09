//! Bounded native-only snapshots of the reviewed Kit configuration.
//! No environment discovery, commands, credentials or network effects occur here.
use crate::{
    digest,
    inventory::{configuration_issues, Inventory, Issue, ProfileIndex},
    strict_json, Result,
};
use std::{
    fs::File,
    io::Read,
    path::{Component, Path, PathBuf},
};

const MAX_FILE: usize = 1_048_576;

#[derive(Clone)]
pub struct Paths {
    inventory: PathBuf,
    index: PathBuf,
    trusted_index: PathBuf,
    kit_ssh: PathBuf,
    user_ssh: PathBuf,
}

fn absolute(path: &Path) -> Result<PathBuf> {
    let mut result = PathBuf::new();
    for part in std::path::absolute(path)
        .map_err(|_| "CONFIGURATION_INVALID")?
        .components()
    {
        match part {
            Component::ParentDir => {
                result.pop();
            }
            Component::CurDir => {}
            part => result.push(part),
        }
    }
    if !result.is_absolute() || result.to_str().is_none() {
        return Err("CONFIGURATION_INVALID");
    }
    #[cfg(windows)]
    {
        result = expand_short_names(&result)?;
    }
    Ok(result)
}
#[cfg(windows)]
fn expand_short_names(path: &Path) -> Result<PathBuf> {
    use std::os::windows::ffi::{OsStrExt, OsStringExt};
    use windows_sys::Win32::Storage::FileSystem::GetLongPathNameW;
    // Windows PowerShell/.NET GetFullPath expands existing 8.3 components,
    // including parents of an absent user SSH file. GetFullPathNameW alone
    // (used by std::path::absolute) does not. Do not canonicalize: that would
    // follow reparse points and introduce a verbatim prefix unlike the Kit.
    let mut result = PathBuf::new();
    for part in path.components() {
        result.push(part.as_os_str());
        if !part.as_os_str().encode_wide().any(|c| c == u16::from(b'~')) {
            continue;
        }
        let input: Vec<u16> = result.as_os_str().encode_wide().chain(Some(0)).collect();
        if input.len() > 32768 {
            return Err("CONFIGURATION_INVALID");
        }
        let mut buffer = vec![0u16; 32768];
        let count =
            unsafe { GetLongPathNameW(input.as_ptr(), buffer.as_mut_ptr(), buffer.len() as u32) }
                as usize;
        if count >= buffer.len() {
            return Err("CONFIGURATION_INVALID");
        }
        // Like .NET's TryExpandShortFileName, retain an unexpandable component;
        // paths may legitimately end in names that do not exist yet.
        if count != 0 {
            result = std::ffi::OsString::from_wide(&buffer[..count]).into();
        }
    }
    Ok(result)
}
fn same_path(a: &Path, b: &Path) -> bool {
    #[cfg(windows)]
    {
        a.to_str()
            .unwrap()
            .eq_ignore_ascii_case(b.to_str().unwrap())
    }
    #[cfg(not(windows))]
    {
        a == b
    }
}
impl Paths {
    /// All paths originate in trusted native configuration, never WebView inputs.
    pub fn new(
        kit: &Path,
        user: &Path,
        inventory: Option<&Path>,
        index: Option<&Path>,
    ) -> Result<Self> {
        let default_inventory = absolute(&kit.join("fleet-inventory.json"))?;
        let inventory = inventory
            .map(absolute)
            .transpose()?
            .unwrap_or(default_inventory.clone());
        if index.is_none() && !same_path(&inventory, &default_inventory) {
            return Err("PROFILE_INDEX_REQUIRED");
        }
        let trusted_index = absolute(&kit.join("bat-profiles/index.json"))?;
        Ok(Self {
            inventory,
            index: index
                .map(absolute)
                .transpose()?
                .unwrap_or(trusted_index.clone()),
            trusted_index,
            kit_ssh: absolute(&kit.join("ssh-config"))?,
            user_ssh: absolute(&user.join(".ssh/config"))?,
        })
    }
}

/// Retain exact bytes for drift checks. A hash cannot identify data read in another generation.
#[derive(Clone, PartialEq, Eq)]
struct Input {
    path: PathBuf,
    bytes: Option<Vec<u8>>,
}
fn read(path: &Path, required: bool) -> Result<Input> {
    match std::fs::metadata(path) {
        Ok(metadata) if metadata.is_file() => {}
        Ok(_) => return Err("CONFIGURATION_INVALID"),
        Err(error) if !required && error.kind() == std::io::ErrorKind::NotFound => {
            return Ok(Input {
                path: path.into(),
                bytes: None,
            });
        }
        Err(_) => return Err("CONFIGURATION_UNREADABLE"),
    }
    let file = match File::open(path) {
        Ok(file) => file,
        Err(error) if !required && error.kind() == std::io::ErrorKind::NotFound => {
            return Ok(Input {
                path: path.into(),
                bytes: None,
            });
        }
        Err(_) => return Err("CONFIGURATION_UNREADABLE"),
    };
    if !file
        .metadata()
        .map_err(|_| "CONFIGURATION_UNREADABLE")?
        .is_file()
    {
        return Err("CONFIGURATION_INVALID");
    }
    let mut bytes = Vec::new();
    file.take((MAX_FILE + 1) as u64)
        .read_to_end(&mut bytes)
        .map_err(|_| "CONFIGURATION_UNREADABLE")?;
    if bytes.len() > MAX_FILE {
        return Err("CONFIGURATION_TOO_LARGE");
    }
    Ok(Input {
        path: path.into(),
        bytes: Some(bytes),
    })
}
fn capture(paths: &Paths) -> Result<Vec<Input>> {
    let mut inputs = vec![
        read(&paths.inventory, true)?,
        read(&paths.index, true)?,
        read(&paths.kit_ssh, true)?,
        read(&paths.user_ssh, false)?,
    ];
    // Alternate profile indexes additionally bind the canonical schema/pin source.
    if !same_path(&paths.index, &paths.trusted_index) {
        inputs.push(read(&paths.trusted_index, true)?);
    }
    Ok(inputs)
}
fn bytes(input: &Input) -> &[u8] {
    let bytes = input.bytes.as_deref().unwrap_or_default();
    bytes.strip_prefix(b"\xef\xbb\xbf").unwrap_or(bytes)
}
fn binding(inputs: &[Input]) -> String {
    // Same default four-input digest as Get-FleetDesktopBinding (UTF-16 path length).
    let mut value = String::from("desktop-configuration-v1\n");
    for input in inputs {
        let path = input.path.to_str().unwrap();
        value.push_str(&format!("{}:{path}:", path.encode_utf16().count()));
        match &input.bytes {
            Some(bytes) => value.push_str(&format!("present:{}\n", digest(bytes))),
            None => value.push_str("absent\n"),
        }
    }
    digest(value.as_bytes())
}

pub struct Configuration {
    paths: Paths,
    inputs: Vec<Input>,
    binding: String,
    pub inventory: Inventory,
    pub profile_index: ProfileIndex,
    pub issues: Vec<Issue>,
}
impl Configuration {
    pub fn load(paths: Paths) -> Result<Self> {
        let inputs = capture(&paths)?;
        let inventory = Inventory::parse(bytes(&inputs[0]))?;
        let canonical = if inputs.len() == 5 {
            &inputs[4]
        } else {
            &inputs[1]
        };
        let schema = strict_json::parse(bytes(canonical), MAX_FILE)?;
        let fields: Vec<_> = schema
            .as_object()
            .ok_or("PROFILE_INDEX_INVALID")?
            .keys()
            .map(String::as_str)
            .collect();
        let trusted = ProfileIndex::parse(bytes(canonical), &fields)?;
        let profile_index = ProfileIndex::parse(bytes(&inputs[1]), &fields)?;
        let ssh = std::str::from_utf8(bytes(&inputs[2])).map_err(|_| "CONFIGURATION_INVALID")?;
        let issues = configuration_issues(&inventory, &profile_index, &trusted, ssh);
        let value = Self {
            paths,
            binding: binding(&inputs),
            inputs,
            inventory,
            profile_index,
            issues,
        };
        value.verify_current()?;
        Ok(value)
    }
    /// Effective paths from the validated pairing, for native monitor identity checks.
    pub fn inventory_path(&self) -> &Path {
        &self.paths.inventory
    }
    pub fn profile_index_path(&self) -> &Path {
        &self.paths.index
    }
    pub fn binding(&self) -> &str {
        &self.binding
    }
    /// Call immediately before local effects and before publishing results derived from this snapshot.
    pub fn verify_current(&self) -> Result<()> {
        if capture(&self.paths).map_err(|_| "CONFIGURATION_CHANGED")? != self.inputs {
            return Err("CONFIGURATION_CHANGED");
        }
        Ok(())
    }
}

/// Re-evaluate for every use: BAT can create the new directory while Fleet is running.
pub fn data_directory(roaming: &Path) -> Result<PathBuf> {
    let latest = absolute(&roaming.join("BetterAgentTerminal"))?;
    let legacy = absolute(&roaming.join("org.tonyq.better-agent-terminal"))?;
    for path in [&latest, &legacy] {
        match std::fs::metadata(path) {
            Ok(metadata) if metadata.is_dir() => return Ok(path.clone()),
            Ok(_) => return Err("DATA_DIRECTORY_INVALID"),
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
            Err(_) => return Err("DATA_DIRECTORY_UNREADABLE"),
        }
    }
    Ok(latest)
}
