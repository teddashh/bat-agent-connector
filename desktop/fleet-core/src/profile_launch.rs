//! Native-only BAT window intent. Does not own or terminate BAT or remote sessions.
use crate::{
    configuration::{data_directory, Configuration},
    digest, inventory, ownership,
    process_adapter::{LoginIdentity, ProcessSnapshot},
    profile_files as index_files,
    selection::launch_plan,
    selection_io::{Snapshot, Store},
    strict_json, supervisor_io as journal_files,
    tunnel::SpawnFailure,
    Result,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::{
    cell::Cell,
    fs::OpenOptions,
    io::Read,
    path::{Path, PathBuf},
};

/// Trusted native path only; Windows constructs this from fixed OS-known candidates.
#[derive(Clone)]
pub struct Executable {
    path: PathBuf,
    digest: String,
}
impl Executable {
    pub fn read(path: &Path) -> Result<Self> {
        if !path.is_absolute() {
            return Err("BAT_EXECUTABLE_UNPROVEN");
        }
        let meta = path
            .symlink_metadata()
            .map_err(|_| "BAT_EXECUTABLE_UNAVAILABLE")?;
        if !meta.is_file() || meta.file_type().is_symlink() || meta.len() > 512 * 1024 * 1024 {
            return Err("BAT_EXECUTABLE_UNPROVEN");
        }
        #[cfg(windows)]
        {
            use std::os::windows::fs::MetadataExt;
            if meta.file_attributes() & 0x400 != 0 || !crate::installation::local_path(path) {
                return Err("BAT_EXECUTABLE_UNPROVEN");
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
            options.custom_flags(0x0020_0000).share_mode(1);
        }
        let mut file = options
            .open(path)
            .map_err(|_| "BAT_EXECUTABLE_UNAVAILABLE")?;
        let opened = file.metadata().map_err(|_| "BAT_EXECUTABLE_UNPROVEN")?;
        if !opened.is_file() || opened.len() != meta.len() {
            return Err("BAT_EXECUTABLE_CHANGED");
        }
        #[cfg(windows)]
        {
            use std::os::windows::fs::MetadataExt;
            if opened.file_attributes() & 0x400 != 0 {
                return Err("BAT_EXECUTABLE_UNPROVEN");
            }
        }
        use sha2::{Digest, Sha256};
        let mut hash = Sha256::new();
        let mut buffer = [0u8; 65536];
        let mut size = 0u64;
        loop {
            let count = file
                .read(&mut buffer)
                .map_err(|_| "BAT_EXECUTABLE_UNAVAILABLE")?;
            if count == 0 {
                break;
            }
            size += count as u64;
            if size > 512 * 1024 * 1024 {
                return Err("BAT_EXECUTABLE_UNPROVEN");
            }
            hash.update(&buffer[..count]);
        }
        if size != opened.len() {
            return Err("BAT_EXECUTABLE_CHANGED");
        }
        Ok(Self {
            path: path.into(),
            digest: format!("{:x}", hash.finalize()),
        })
    }
    pub fn verify(&self) -> Result<()> {
        let actual = Self::read(&self.path)?;
        if actual.digest != self.digest {
            return Err("BAT_EXECUTABLE_CHANGED");
        }
        Ok(())
    }
    pub fn path(&self) -> &Path {
        &self.path
    }
    fn matches(&self, process: &ProcessSnapshot) -> bool {
        process.valid()
            && process.arguments.is_empty()
            && self
                .path
                .to_str()
                .is_some_and(|path| path.eq_ignore_ascii_case(&process.executable))
    }
}

/// Caller retains its launcher guard. No shell, arbitrary args, kill or focus operation exists.
pub trait Platform {
    fn verify(&self) -> Result<()>;
    fn login(&self) -> Result<LoginIdentity>;
    fn executable(&self) -> Result<Executable>;
    /// Complete BAT candidates; inaccessible candidates refuse, never disappear from the list.
    fn running(&self) -> Result<Vec<ProcessSnapshot>>;
    fn observe(&self, pid: u32) -> Result<Option<ProcessSnapshot>>;
    fn spawn(
        &mut self,
        executable: &Executable,
    ) -> std::result::Result<ProcessSnapshot, SpawnFailure>;
}

#[derive(Clone, Serialize)]
pub struct Summary {
    pub launch_id: String,
    pub profiles: Vec<String>,
    pub dashboard: bool,
    pub opens_bat: bool,
    pub already_running: bool,
    pub bat_may_open_local_window: bool,
}
/// Retained in Rust behind an opaque handle; raw index bytes/path are never serialized to UI.
pub struct Preview {
    summary: Summary,
    selection: Snapshot,
    login: LoginIdentity,
    directory: PathBuf,
    roaming: PathBuf,
    executable: Option<Executable>,
    original: zeroize::Zeroizing<Vec<u8>>,
    proposed: zeroize::Zeroizing<Vec<u8>>,
    attempted: Cell<bool>,
}
impl Preview {
    pub fn summary(&self) -> Summary {
        self.summary.clone()
    }
}

fn index(configuration: &Configuration, bytes: &[u8], selected: &[String]) -> Result<Vec<u8>> {
    let mut doc = strict_json::parse(
        bytes.strip_prefix(b"\xef\xbb\xbf").unwrap_or(bytes),
        index_files::LIMIT,
    )
    .map_err(|_| "PROFILE_INDEX_UNPROVEN")?;
    let profiles = doc
        .get("profiles")
        .and_then(Value::as_array)
        .filter(|p| p.len() <= 10000)
        .ok_or("PROFILE_INDEX_UNPROVEN")?;
    let mut seen = std::collections::HashSet::new();
    for profile in profiles {
        let id = profile
            .get("id")
            .and_then(Value::as_str)
            .filter(|id| !id.is_empty() && id.len() <= 256 && !id.contains('\0'))
            .ok_or("PROFILE_INDEX_UNPROVEN")?;
        if !seen.insert(id.to_lowercase()) {
            return Err("PROFILE_INDEX_UNPROVEN");
        }
        // Pinned BAT ProfileEntry types: otherwise BAT can read its backup/default
        // index instead of the reviewed selection. Unknown metadata is preserved.
        if profile.get("name").and_then(Value::as_str).is_none()
            || profile.get("type").and_then(Value::as_str).is_none()
            || ["createdAt", "updatedAt"]
                .iter()
                .any(|key| profile.get(*key).and_then(Value::as_i64).is_none())
            || [
                "remoteHost",
                "remoteToken",
                "remoteFingerprint",
                "remoteProfileId",
                "remoteProfileName",
                "sshTarget",
            ]
            .iter()
            .any(|key| {
                profile
                    .get(*key)
                    .is_some_and(|value| !value.is_null() && !value.is_string())
            })
            || profile.get("remotePort").is_some_and(|value| {
                !value.is_null()
                    && !value
                        .as_u64()
                        .is_some_and(|port| port <= u64::from(u32::MAX))
            })
        {
            return Err("PROFILE_INDEX_UNPROVEN");
        }
    }
    if doc
        .get("activeProfileId")
        .is_some_and(|value| !value.is_null() && !value.is_string())
    {
        return Err("PROFILE_INDEX_UNPROVEN");
    }
    for id in selected {
        let actual = profiles
            .iter()
            .find(|p| p["id"] == *id)
            .ok_or("PROFILE_DRIFT")?;
        if actual["name"]
            .as_str()
            .is_none_or(|name| name.trim().is_empty())
            || actual
                .get("sshTarget")
                .and_then(Value::as_str)
                .is_some_and(|value| !value.trim().is_empty())
        {
            return Err("PROFILE_DRIFT");
        }
        if id == "default" {
            if actual["type"] != "local" {
                return Err("PROFILE_DRIFT");
            }
            continue;
        }
        let expected = configuration
            .profile_index
            .profile(id)
            .ok_or("PROFILE_DRIFT")?;
        for field in ["type", "remoteHost", "remotePort"] {
            if actual[field] != expected[field] {
                return Err("PROFILE_DRIFT");
            }
        }
        let remote = |p: &Value| {
            p.get("remoteProfileId")
                .and_then(Value::as_str)
                .filter(|value| !value.is_empty())
                .unwrap_or("default")
                .to_owned()
        };
        let pin = |p: &Value| p["remoteFingerprint"].as_str().and_then(inventory::pin);
        if remote(actual) != remote(expected)
            || pin(actual).is_none()
            || pin(actual) != pin(expected)
        {
            return Err("PROFILE_DRIFT");
        }
    }
    doc["activeProfileIds"] =
        serde_json::to_value(selected).map_err(|_| "PROFILE_INDEX_UNPROVEN")?;
    let bytes = serde_json::to_vec_pretty(&doc).map_err(|_| "PROFILE_INDEX_UNPROVEN")?;
    if bytes.len() > index_files::LIMIT {
        return Err("PROFILE_INDEX_UNPROVEN");
    }
    Ok(bytes)
}
fn check(
    configuration: &Configuration,
    store: &Store,
    preview: &Preview,
    platform: &impl Platform,
) -> Result<()> {
    platform.verify()?;
    if platform.login()? != preview.login {
        return Err("OTHER_LOGIN_OWNER");
    }
    configuration.verify_current()?;
    if preview.selection.configuration_binding() != configuration.binding() {
        return Err("CONFIGURATION_CHANGED");
    }
    if !preview.selection.same_snapshot(&store.read(configuration)?) {
        return Err("SELECTION_CHANGED");
    }
    if data_directory(&preview.roaming)? != preview.directory {
        return Err("DATA_DIRECTORY_CHANGED");
    }
    index_files::directory(&preview.directory)?;
    Ok(())
}
fn absence(platform: &impl Platform, login: &LoginIdentity) -> Result<bool> {
    let processes = platform.running()?;
    if processes.len() > 1024 || processes.iter().any(|p| !p.valid()) {
        return Err("BAT_PROCESS_UNPROVEN");
    }
    if processes.iter().any(|p| p.login != *login) {
        return Err("OTHER_LOGIN_OWNER");
    }
    Ok(processes.is_empty())
}
pub fn preview(
    configuration: &Configuration,
    store: &Store,
    selection: &Snapshot,
    roaming: &Path,
    platform: &impl Platform,
) -> Result<Preview> {
    let plan = launch_plan(&configuration.inventory, selection.preferences());
    preview_profiles(
        configuration,
        store,
        selection,
        roaming,
        platform,
        plan.open,
        plan.dashboard,
    )
}

/// One explicit profile, without rewriting the saved Fleet window/connection choices.
/// The unchanged private selection still fences both preview and final launch.
pub fn preview_profile(
    configuration: &Configuration,
    store: &Store,
    selection: &Snapshot,
    roaming: &Path,
    platform: &impl Platform,
    profile_id: &str,
) -> Result<Preview> {
    if profile_id != "default" {
        let host = configuration
            .inventory
            .hosts()
            .iter()
            .find(|host| host["profile"].as_str() == Some(profile_id))
            .ok_or("PROFILE_DRIFT")?;
        let plan = launch_plan(&configuration.inventory, selection.preferences());
        if !plan.connect.iter().any(|name| host["name"] == *name) {
            return Err("PROFILE_CONNECTION_NOT_SELECTED");
        }
    }
    preview_profiles(
        configuration,
        store,
        selection,
        roaming,
        platform,
        vec![profile_id.into()],
        false,
    )
}

fn preview_profiles(
    configuration: &Configuration,
    store: &Store,
    selection: &Snapshot,
    roaming: &Path,
    platform: &impl Platform,
    profiles: Vec<String>,
    dashboard: bool,
) -> Result<Preview> {
    platform.verify()?;
    let login = platform.login()?;
    if !login.valid() || !roaming.is_absolute() {
        return Err("INVALID_REQUEST");
    }
    let mut preview = Preview {
        summary: Summary {
            launch_id: format!("{:032x}", rand::random::<u128>()),
            opens_bat: !profiles.is_empty(),
            bat_may_open_local_window: !profiles.is_empty()
                && !profiles.iter().any(|id| id == "default"),
            profiles,
            dashboard,
            already_running: false,
        },
        selection: selection.clone(),
        login,
        directory: selection.directory().into(),
        roaming: roaming.into(),
        executable: None,
        original: zeroize::Zeroizing::new(vec![]),
        proposed: zeroize::Zeroizing::new(vec![]),
        attempted: Cell::new(false),
    };
    check(configuration, store, &preview, platform)?;
    if !preview.summary.opens_bat {
        return Ok(preview);
    }
    if !absence(platform, &preview.login)? {
        preview.summary.already_running = true;
        return Ok(preview);
    }
    if !configuration.issues.is_empty() {
        return Err("CONFIGURATION_INVALID");
    }
    preview.executable = Some(platform.executable()?);
    let path = preview.directory.join("profiles/index.json");
    preview.original = zeroize::Zeroizing::new(index_files::read(&path)?);
    preview.proposed = zeroize::Zeroizing::new(index(
        configuration,
        &preview.original,
        &preview.summary.profiles,
    )?);
    check(configuration, store, &preview, platform)?;
    if index_files::read(&path)? != *preview.original {
        return Err("PROFILE_INDEX_CHANGED");
    }
    Ok(preview)
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum State {
    Prepared,
    Uncertain,
    Started,
    NotStarted,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Birth {
    pid: u32,
    created_filetime: u64,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Intent {
    schema_version: u32,
    id: String,
    owner_sid: String,
    session_id: u32,
    configuration_binding: String,
    selection_revision: String,
    profiles: Vec<String>,
    dashboard: bool,
    executable: String,
    image_digest: String,
    index_before: String,
    index_after: String,
    state: State,
    code: Option<String>,
    child: Option<Birth>,
}
impl Intent {
    fn login(&self) -> LoginIdentity {
        LoginIdentity {
            owner_sid: self.owner_sid.clone(),
            session_id: self.session_id,
        }
    }
    fn parse(bytes: &[u8]) -> Result<Self> {
        let v: Self = serde_json::from_value(strict_json::parse(bytes, 262144)?)
            .map_err(|_| "BAT_LAUNCH_UNPROVEN")?;
        let hex = |s: &str, n| s.len() == n && s.bytes().all(|b| b.is_ascii_hexdigit());
        if v.schema_version != 1
            || !ownership::epoch_valid(&v.id)
            || !v.login().valid()
            || [
                &v.configuration_binding,
                &v.selection_revision,
                &v.image_digest,
                &v.index_before,
                &v.index_after,
            ]
            .iter()
            .any(|s| !hex(s, 64))
            || v.profiles.is_empty()
            || v.profiles.len() > 1000
            || v.profiles.iter().any(|p| {
                p.is_empty()
                    || p.len() > 64
                    || !p
                        .bytes()
                        .all(|b| b.is_ascii_alphanumeric() || b"_.-".contains(&b))
            })
            || v.executable.is_empty()
            || v.executable.len() > 32768
            || v.executable.contains('\0')
            || v.child.as_ref().is_some_and(|b| {
                b.pid == 0 || crate::process_adapter::datetime_ticks(b.created_filetime).is_err()
            })
            || (v.state == State::Started) != v.child.is_some()
            || v.code.as_ref().is_some_and(|code| {
                code.is_empty()
                    || code.len() > 80
                    || !code
                        .bytes()
                        .all(|b| b.is_ascii_uppercase() || b.is_ascii_digit() || b == b'_')
            })
        {
            return Err("BAT_LAUNCH_UNPROVEN");
        }
        Ok(v)
    }
    fn bytes(&self) -> Result<Vec<u8>> {
        serde_json::to_vec(self).map_err(|_| "BAT_LAUNCH_UNPROVEN")
    }
    fn receipt(&self) -> Receipt {
        Receipt {
            launch_id: self.id.clone(),
            profiles: self.profiles.clone(),
            dashboard: self.dashboard,
            code: if self.state == State::Prepared {
                Some("BAT_LAUNCH_UNCONFIRMED".into())
            } else {
                self.code.clone()
            },
            state: if self.state == State::Prepared {
                State::Uncertain
            } else {
                self.state.clone()
            },
        }
    }
}
/// A creation receipt does not prove that BAT rendered a window or connected to any host.
#[derive(Serialize)]
pub struct Receipt {
    pub launch_id: String,
    pub profiles: Vec<String>,
    pub dashboard: bool,
    pub state: State,
    pub code: Option<String>,
}
pub enum Outcome {
    NoBat(Summary),
    AlreadyRunning(Summary),
    Receipt(Receipt),
}
fn journal(roaming: &Path) -> Result<PathBuf> {
    if !roaming.is_absolute() {
        return Err("INVALID_REQUEST");
    }
    index_files::directory(roaming)?;
    Ok(roaming.join("bat-fleet-profile-launch.json"))
}
/// Readback survives changed activeProfileIds after BAT startup. It never replays a spawn.
pub fn read_receipt(roaming: &Path, id: &str, platform: &impl Platform) -> Result<Option<Receipt>> {
    Ok(read_intent(roaming, id, platform)?.map(|intent| intent.receipt()))
}
fn read_intent(roaming: &Path, id: &str, platform: &impl Platform) -> Result<Option<Intent>> {
    platform.verify()?;
    if !ownership::epoch_valid(id) {
        return Err("INVALID_REQUEST");
    }
    let current = journal_files::read(&journal(roaming)?)?;
    let current = current.as_deref().map(Intent::parse).transpose()?;
    let intent = if let Some(intent) = current.filter(|intent| intent.id == id) {
        intent
    } else {
        let Some(bytes) = journal_files::read(
            &roaming
                .join("bat-fleet-profile-launches")
                .join(format!("{id}.json")),
        )?
        else {
            return Ok(None);
        };
        let intent = Intent::parse(&bytes)?;
        if intent.id != id {
            return Err("BAT_LAUNCH_UNPROVEN");
        }
        intent
    };
    if intent.login() != platform.login()? {
        return Err("OTHER_LOGIN_OWNER");
    }
    Ok(Some(intent))
}

pub fn apply(
    configuration: &Configuration,
    store: &Store,
    preview: &Preview,
    platform: &mut impl Platform,
) -> Result<Outcome> {
    platform.verify()?;
    if preview.login != platform.login()? {
        return Err("OTHER_LOGIN_OWNER");
    }
    // An unrelated BAT receipt must not prevent a Dashboard-only launch.
    if !preview.summary.opens_bat {
        check(configuration, store, preview, platform)?;
        return Ok(Outcome::NoBat(preview.summary()));
    }
    if let Some(intent) = read_intent(&preview.roaming, &preview.summary.launch_id, platform)? {
        if intent.profiles != preview.summary.profiles
            || intent.dashboard != preview.summary.dashboard
            || intent.configuration_binding != preview.selection.configuration_binding()
            || intent.selection_revision != preview.selection.revision
            || intent.index_before != digest(&preview.original)
            || intent.index_after != digest(&preview.proposed)
            || !preview.executable.as_ref().is_some_and(|image| {
                image.digest == intent.image_digest
                    && image.path.to_str() == Some(intent.executable.as_str())
            })
        {
            return Err("BAT_LAUNCH_UNPROVEN");
        }
        return Ok(Outcome::Receipt(intent.receipt()));
    }
    if preview.attempted.get() {
        return Err("BAT_LAUNCH_UNCONFIRMED");
    }
    check(configuration, store, preview, platform)?;
    if preview.summary.already_running || !absence(platform, &preview.login)? {
        let mut summary = preview.summary();
        summary.already_running = true;
        return Ok(Outcome::AlreadyRunning(summary));
    }
    let executable = preview
        .executable
        .as_ref()
        .ok_or("BAT_EXECUTABLE_UNPROVEN")?;
    executable.verify()?;
    let path = journal(&preview.roaming)?;
    let previous = journal_files::read(&path)?;
    if let Some(bytes) = &previous {
        let old = Intent::parse(bytes)?;
        if old.login() != preview.login {
            return Err("OTHER_LOGIN_OWNER");
        }
        if old.state != State::NotStarted {
            let child = old.child.ok_or("BAT_LAUNCH_UNCONFIRMED")?;
            if platform
                .observe(child.pid)?
                .is_some_and(|p| p.created_filetime == child.created_filetime)
            {
                return Err("BAT_LAUNCH_UNCONFIRMED");
            }
        }
        // Keep historical IDs replayable even after a later explicit launch.
        let archive = preview
            .roaming
            .join("bat-fleet-profile-launches")
            .join(format!("{}.json", old.id));
        match journal_files::read(&archive)? {
            Some(saved) if saved == *bytes => (),
            Some(_) => return Err("BAT_LAUNCH_UNPROVEN"),
            None => journal_files::replace(&archive, None, bytes, || platform.verify())?,
        }
    }
    let index_path = preview.directory.join("profiles/index.json");
    let before = || {
        check(configuration, store, preview, platform)?;
        if !absence(platform, &preview.login)? {
            return Err("BAT_ALREADY_RUNNING");
        }
        executable.verify()
    };
    before()?;
    if index_files::read(&index_path)? != *preview.original {
        return Err("PROFILE_INDEX_CHANGED");
    }
    let mut intent = Intent {
        schema_version: 1,
        id: preview.summary.launch_id.clone(),
        owner_sid: preview.login.owner_sid.clone(),
        session_id: preview.login.session_id,
        configuration_binding: configuration.binding().into(),
        selection_revision: preview.selection.revision.clone(),
        profiles: preview.summary.profiles.clone(),
        dashboard: preview.summary.dashboard,
        executable: executable
            .path
            .to_str()
            .ok_or("BAT_EXECUTABLE_UNPROVEN")?
            .into(),
        image_digest: executable.digest.clone(),
        index_before: digest(&preview.original),
        index_after: digest(&preview.proposed),
        state: State::Prepared,
        code: None,
        child: None,
    };
    let mut bytes = intent.bytes()?;
    Intent::parse(&bytes)?;
    journal_files::replace(&path, previous.as_deref(), &bytes, before)?;
    preview.attempted.set(true);
    let prepare = (|| {
        index_files::replace(&index_path, &preview.original, &preview.proposed, before)?;
        intent.state = State::Uncertain;
        intent.code = Some("BAT_LAUNCH_UNCONFIRMED".into());
        let sent = intent.bytes()?;
        journal_files::replace(&path, Some(&bytes), &sent, before)?;
        bytes = sent;
        before()?;
        if index_files::read(&index_path)? != *preview.proposed {
            return Err("PROFILE_INDEX_CHANGED");
        }
        Ok(())
    })();
    if let Err(error) = prepare {
        // No spawn was invoked. Restore only our exact bytes while BAT is absent.
        let _ = index_files::replace(&index_path, &preview.proposed, &preview.original, before);
        intent.state = State::NotStarted;
        intent.code = Some(error.into());
        journal_files::replace(&path, Some(&bytes), &intent.bytes()?, || Ok(()))?;
        return Ok(Outcome::Receipt(intent.receipt()));
    }
    match platform.spawn(executable) {
        Ok(child) if executable.matches(&child) && child.login == preview.login => {
            intent.child = Some(Birth {
                pid: child.pid,
                created_filetime: child.created_filetime,
            });
            intent.state = State::Started;
            intent.code = None;
        }
        Err(SpawnFailure::NotStarted | SpawnFailure::RolledBack) => {
            let _ = index_files::replace(&index_path, &preview.proposed, &preview.original, || {
                platform.verify()?;
                if platform.login() != Ok(preview.login.clone())
                    || !absence(platform, &preview.login)?
                {
                    return Err("BAT_PROCESS_UNPROVEN");
                }
                Ok(())
            });
            intent.state = State::NotStarted;
            intent.code = Some("BAT_START_FAILED".into());
        }
        _ => return Ok(Outcome::Receipt(intent.receipt())),
    }
    // Capture sent-effect evidence even if unrelated configuration changed after creation.
    journal_files::replace(&path, Some(&bytes), &intent.bytes()?, || Ok(()))?;
    Ok(Outcome::Receipt(intent.receipt()))
}
