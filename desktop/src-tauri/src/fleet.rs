//! Fixed local Fleet transport. The configured backend remains the only tunnel owner.
use bat_fleet_core::{discovery::Backend, installation::Snapshot};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    collections::HashSet,
    path::{Path, PathBuf},
    process::Stdio,
    sync::atomic::{AtomicU64, Ordering},
    time::Duration,
};
use tokio::{
    io::{AsyncReadExt, AsyncWriteExt},
    process::Command,
    sync::Mutex,
};

const MAX_INPUT: usize = 65_536;
const MAX_OUTPUT: usize = 262_144;
const ACTIONS: [&str; 6] = [
    "contract",
    "status",
    "validate_configuration",
    "set_connections",
    "ensure_monitor",
    "quit_owned",
];
static REQUEST: AtomicU64 = AtomicU64::new(1);

#[derive(Debug, Deserialize)]
#[serde(tag = "action", rename_all = "snake_case", deny_unknown_fields)]
pub enum FleetRequest {
    Contract {},
    Status {},
    ValidateConfiguration {},
    SetConnections {
        connections: Vec<String>,
        expected_configuration_binding: String,
        expected_selection_revision: String,
        expected_monitor_epoch: Option<String>,
    },
    EnsureMonitor {
        expected_configuration_binding: String,
    },
    QuitOwned {
        expected_configuration_binding: String,
        expected_monitor_epoch: String,
    },
}

impl FleetRequest {
    fn envelope(&self, id: &str) -> Result<Value, String> {
        let action = match self {
            Self::Contract {} => "contract",
            Self::Status {} => "status",
            Self::ValidateConfiguration {} => "validate_configuration",
            Self::SetConnections { .. } => "set_connections",
            Self::EnsureMonitor { .. } => "ensure_monitor",
            Self::QuitOwned { .. } => "quit_owned",
        };
        let mut body = json!({"schema_version":1,"request_id":id,"action":action});
        match self {
            Self::SetConnections {
                connections,
                expected_configuration_binding,
                expected_selection_revision,
                expected_monitor_epoch,
            } => {
                let unique: HashSet<_> = connections.iter().collect();
                if connections.len() > 1000
                    || unique.len() != connections.len()
                    || connections.iter().any(|s| !identifier(s, 128))
                    || !hex(expected_selection_revision, 64)
                    || !hex(expected_configuration_binding, 64)
                    || expected_monitor_epoch.as_ref().is_some_and(|s| !hex(s, 32))
                {
                    return Err("Invalid Fleet selection or version".into());
                }
                body["connections"] = json!(connections);
                body["expected_configuration_binding"] = json!(expected_configuration_binding);
                body["expected_selection_revision"] = json!(expected_selection_revision);
                body["expected_monitor_epoch"] = json!(expected_monitor_epoch);
            }
            Self::QuitOwned {
                expected_configuration_binding,
                expected_monitor_epoch,
            } => {
                if !hex(expected_monitor_epoch, 32) || !hex(expected_configuration_binding, 64) {
                    return Err("Invalid Fleet monitor version".into());
                }
                body["expected_monitor_epoch"] = json!(expected_monitor_epoch);
                body["expected_configuration_binding"] = json!(expected_configuration_binding);
            }
            Self::EnsureMonitor {
                expected_configuration_binding,
            } => {
                if !hex(expected_configuration_binding, 64) {
                    return Err("Invalid Fleet configuration version".into());
                }
                body["expected_configuration_binding"] = json!(expected_configuration_binding);
            }
            _ => {}
        }
        Ok(body)
    }
}

fn identifier(s: &str, max: usize) -> bool {
    !s.is_empty()
        && s.len() <= max
        && s.bytes()
            .all(|b| b.is_ascii_alphanumeric() || b"_-.:".contains(&b))
}
fn hex(s: &str, len: usize) -> bool {
    s.len() == len
        && s.bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

#[derive(Serialize)]
pub struct FleetAvailability {
    pub configured: bool,
    pub platform_supported: bool,
    pub error: Option<String>,
}

pub struct FleetBridge {
    config: PathBuf,
    serial: Mutex<()>,
}

impl FleetBridge {
    pub fn load(config_dir: &Path) -> Self {
        Self::load_path(config_dir.join("fleet.json"))
    }
    pub fn load_path(config: PathBuf) -> Self {
        Self {
            config,
            serial: Mutex::new(()),
        }
    }
    pub fn availability(&self) -> FleetAvailability {
        let installation = Snapshot::load(&self.config);
        FleetAvailability {
            configured: installation.is_ok(),
            platform_supported: cfg!(windows),
            error: installation
                .err()
                .map(|code| format!("Fleet configuration unavailable ({code})")),
        }
    }
    pub async fn request(&self, input: FleetRequest) -> Result<Value, String> {
        // Validate before any local effect; IPC never supplies paths, PID, commands or credentials.
        let id = format!("desktop_{}", REQUEST.fetch_add(1, Ordering::Relaxed));
        let request = input.envelope(&id)?;
        let _guard = self
            .serial
            .try_lock()
            .map_err(|_| "Fleet request already in progress; read status before retrying")?;
        // Migration may change backend while the Dashboard remains open. Capture fresh trusted bytes.
        let installation = Snapshot::load(&self.config).map_err(native_error)?;
        if installation.backend() == Backend::Rust {
            #[cfg(windows)]
            {
                return tokio::task::spawn_blocking(move || {
                    crate::fleet_native::request(installation, input)
                })
                .await
                .map_err(|_| "Fleet outcome unknown; read status before retrying")?;
            }
            #[cfg(not(windows))]
            {
                return Err("Fleet desktop control requires Windows".into());
            }
        }
        #[cfg(windows)]
        if matches!(
            input,
            FleetRequest::SetConnections { .. }
                | FleetRequest::EnsureMonitor { .. }
                | FleetRequest::QuitOwned { .. }
        ) {
            return tokio::task::spawn_blocking(move || {
                // The Kit's desktop facade does not hold its launcher mutex. Keep it on this
                // blocking thread through validation, subprocess effect and bounded readback.
                let _launcher = bat_fleet_core::windows_launcher::LauncherMutex::try_acquire()
                    .map_err(native_error)?
                    .ok_or_else(|| native_error("LAUNCHER_BUSY"))?;
                installation.verify_current().map_err(native_error)?;
                crate::fleet_native::verify_no_migration(&installation).map_err(native_error)?;
                let runtime = tokio::runtime::Builder::new_current_thread()
                    .enable_all()
                    .build()
                    .map_err(|_| native_error("SUPERVISOR_UNAVAILABLE"))?;
                runtime.block_on(powershell_request(installation, request, id))
            })
            .await
            .map_err(|_| native_error("OUTCOME_UNKNOWN"))?;
        }
        powershell_request(installation, request, id).await
    }
}
async fn powershell_request(
    installation: Snapshot,
    request: Value,
    id: String,
) -> Result<Value, String> {
    let script = powershell_path(installation.script().to_path_buf())?;
    let executable = powershell()?;
    let contract_id = format!("{id}_contract");
    let contract = json!({"schema_version":1,"request_id":contract_id,"action":"contract"});
    installation.verify_current().map_err(native_error)?;
    let result = call(&executable, &script, &contract, Duration::from_secs(10)).await?;
    verify_contract(&result)?;
    installation.verify_current().map_err(native_error)?;
    if request["action"] == "contract" {
        return Ok(result);
    }
    let result = call(&executable, &script, &request, Duration::from_secs(35)).await?;
    installation.verify_current().map_err(native_error)?;
    Ok(result)
}
fn native_error(code: &str) -> String {
    format!("Fleet refused the request ({code}); read status before retrying")
}
#[cfg(test)]
fn load_script(config: &Path) -> Result<PathBuf, String> {
    let installation = Snapshot::load(config).map_err(native_error)?;
    powershell_path(installation.script().to_path_buf())
}

#[cfg(windows)]
fn powershell_path(path: PathBuf) -> Result<PathBuf, String> {
    use std::os::windows::ffi::{OsStrExt, OsStringExt};
    use std::path::{Component, Prefix};
    let units: Vec<_> = path.as_os_str().encode_wide().collect();
    // PowerShell5.1 accepts ordinary local paths; avoid passing Rust's verbatim path spelling.
    let start = match path.components().next() {
        Some(Component::Prefix(p)) if matches!(p.kind(), Prefix::VerbatimDisk(_)) => 4,
        _ => 0,
    };
    if units.len() - start > 240 {
        return Err("Fleet Kit installation path is too long for Windows PowerShell".into());
    }
    Ok(PathBuf::from(std::ffi::OsString::from_wide(
        &units[start..],
    )))
}
#[cfg(not(windows))]
fn powershell_path(path: PathBuf) -> Result<PathBuf, String> {
    Ok(path)
}

#[cfg(windows)]
fn powershell() -> Result<PathBuf, String> {
    #[link(name = "kernel32")]
    extern "system" {
        fn GetSystemDirectoryW(buffer: *mut u16, size: u32) -> u32;
    }
    let mut buffer = [0u16; 32_768];
    // OS API supplies the system directory; neither PATH nor WebView chooses the executable.
    let count = unsafe { GetSystemDirectoryW(buffer.as_mut_ptr(), buffer.len() as u32) } as usize;
    if count == 0 || count >= buffer.len() {
        return Err("Windows PowerShell is unavailable".into());
    }
    use std::os::windows::ffi::OsStringExt;
    let path = PathBuf::from(std::ffi::OsString::from_wide(&buffer[..count]))
        .join("WindowsPowerShell/v1.0/powershell.exe");
    if !path.is_file() {
        return Err("Windows PowerShell is unavailable".into());
    }
    Ok(path)
}
#[cfg(not(windows))]
fn powershell() -> Result<PathBuf, String> {
    Err("Fleet desktop control requires Windows".into())
}

async fn call(
    executable: &Path,
    script: &Path,
    request: &Value,
    deadline: Duration,
) -> Result<Value, String> {
    let command = adapter_command(executable, script)?;
    let bytes = run_command(command, request, deadline).await?;
    parse_response(&bytes, request)
}

fn adapter_command(executable: &Path, script: &Path) -> Result<Command, String> {
    let mut command = Command::new(executable);
    command
        .args([
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
        ])
        .arg(script);
    command.current_dir(
        script
            .parent()
            .ok_or("Fleet adapter directory is unavailable")?,
    );
    // No inherited Connector/BAT tokens or proxy credentials. Preserve only Windows identity paths.
    command.env_clear();
    for name in [
        "APPDATA",
        "LOCALAPPDATA",
        "USERPROFILE",
        "USERNAME",
        "USERDOMAIN",
        "TEMP",
        "TMP",
        "HOMEDRIVE",
        "HOMEPATH",
        "PROGRAMDATA",
        "PROGRAMFILES",
        "COMMONPROGRAMFILES",
        "SYSTEMDRIVE",
    ] {
        if let Some(value) = std::env::var_os(name) {
            command.env(name, value);
        }
    }
    if let Some(system) = executable
        .parent()
        .and_then(Path::parent)
        .and_then(Path::parent)
    {
        command.env("PATH", system);
        // Use the modules shipped with this OS-selected PowerShell only. Do not inherit
        // user module paths (or PowerShell 7's paths when launched by a different host).
        command.env("PSModulePath", executable.parent().unwrap().join("Modules"));
        if let Some(windows) = system.parent() {
            command.env("SystemRoot", windows).env("WINDIR", windows);
        }
    }
    #[cfg(windows)]
    command.creation_flags(0x0800_0000); // CREATE_NO_WINDOW; monitor bootstrap owns its own lifecycle.
    Ok(command)
}

async fn run_command(
    mut command: Command,
    request: &Value,
    deadline: Duration,
) -> Result<Vec<u8>, String> {
    let input = serde_json::to_vec(request).map_err(|_| "Invalid Fleet request")?;
    if input.len() > MAX_INPUT {
        return Err("Fleet request exceeds its bound".into());
    }
    command
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .kill_on_drop(true);
    let work = async {
        let mut child = command
            .spawn()
            .map_err(|_| "Unable to start the Fleet adapter")?;
        let mut stdin = child
            .stdin
            .take()
            .ok_or("Fleet adapter stdin unavailable")?;
        let stdout = child
            .stdout
            .take()
            .ok_or("Fleet adapter stdout unavailable")?;
        let write = async {
            stdin.write_all(&input).await?;
            stdin.shutdown().await?;
            drop(stdin); // The facade reads until EOF before decoding its one JSON request.
            Ok::<_, std::io::Error>(())
        };
        let read = async {
            let mut bytes = Vec::new();
            stdout
                .take(MAX_OUTPUT as u64 + 1)
                .read_to_end(&mut bytes)
                .await?;
            Ok::<_, std::io::Error>(bytes)
        };
        let (_, bytes) = tokio::try_join!(write, read)
            .map_err(|_| "Fleet adapter transport failed; read status before retrying")?;
        if bytes.len() > MAX_OUTPUT {
            return Err("Fleet response exceeds its bound".into());
        }
        // The envelope distinguishes refusal from success; nonzero exit alone is not an outcome.
        let status = child
            .wait()
            .await
            .map_err(|_| "Fleet adapter outcome is unknown; read status before retrying")?;
        let value: Value = serde_json::from_slice(&bytes)
            .map_err(|_| "Invalid Fleet response; read status before retrying")?;
        if status.success() != (value.get("ok") == Some(&Value::Bool(true))) {
            return Err("Fleet adapter outcome is unknown; read status before retrying".into());
        }
        Ok(bytes)
    };
    tokio::time::timeout(deadline, work)
        .await
        .map_err(|_| "Fleet request timed out; read status before retrying")?
}

fn verify_contract(result: &Value) -> Result<(), String> {
    let supported = result["supported_actions"]
        .as_array()
        .ok_or("Unsupported Fleet adapter contract")?;
    if result["implementation"] != "bat-fleet-kit"
        || result["implementation_version"] != "desktop-facade-v1"
        || result["schema_version"] != 1
        || result["platform"] != "windows"
        || result["platform_supported"] != true
        || result["max_request_bytes"] != MAX_INPUT
        || result["max_response_bytes"] != MAX_OUTPUT
        || result["readiness_max_age_s"] != 60
        || supported.len() != ACTIONS.len()
        || ACTIONS.iter().any(|a| !supported.contains(&json!(a)))
    {
        return Err("Unsupported Fleet adapter contract".into());
    }
    Ok(())
}

fn parse_response(bytes: &[u8], request: &Value) -> Result<Value, String> {
    if bytes.len() > MAX_OUTPUT {
        return Err("Fleet response exceeds its bound".into());
    }
    let body: Value = serde_json::from_slice(bytes)
        .map_err(|_| "Invalid Fleet response; read status before retrying")?;
    if body["schema_version"] != 1
        || body["request_id"] != request["request_id"]
        || !body["ok"].is_boolean()
    {
        return Err("Invalid Fleet response identity; read status before retrying".into());
    }
    if body["ok"] == false {
        // Do not display subprocess-provided text, paths, stack traces or credentials.
        let code = body["error"]["code"]
            .as_str()
            .filter(|s| {
                [
                    "INVALID_REQUEST",
                    "PLATFORM_UNSUPPORTED",
                    "CONFIGURATION_INVALID",
                    "CONFIGURATION_CHANGED",
                    "INVALID_SELECTION",
                    "SELECTION_CHANGED",
                    "SELECTION_BUSY",
                    "MONITOR_EPOCH_CHANGED",
                    "MONITOR_OTHER_SESSION",
                    "MONITOR_NOT_RUNNING",
                    "MONITOR_INVENTORY_MISMATCH",
                    "OWNER_UNPROVEN",
                    "INVENTORY_NOT_CONFIGURED",
                    "INVENTORY_INVALID",
                    "INVENTORY_SCHEMA_UNSUPPORTED",
                    "PROFILE_INDEX_REQUIRED",
                    "PROFILE_INDEX_INVALID",
                    "STATUS_TOO_LARGE",
                    "INTERNAL",
                ]
                .contains(s)
            })
            .unwrap_or("INTERNAL");
        return Err(format!(
            "Fleet refused the request ({code}); read status before retrying"
        ));
    }
    sanitize_result(&body["result"], request["action"].as_str().unwrap_or(""))
}

// Construct the output field by field; additions to the Kit contract never silently enter IPC.
pub(crate) fn sanitize_result(value: &Value, action: &str) -> Result<Value, String> {
    let invalid = || "Invalid Fleet result; read status before retrying".to_owned();
    match action {
        "contract" => {
            verify_contract(value)?;
            Ok(
                json!({"implementation":"bat-fleet-kit","implementation_version":"desktop-facade-v1","schema_version":1,"platform":"windows","platform_supported":true,"supported_actions":ACTIONS,"max_request_bytes":MAX_INPUT,"max_response_bytes":MAX_OUTPUT,"readiness_max_age_s":60}),
            )
        }
        "validate_configuration" => configuration(value),
        "quit_owned" => {
            let epoch = value["monitor_epoch"]
                .as_str()
                .filter(|s| hex(s, 32))
                .ok_or_else(invalid)?;
            if value["requested"] != true || value["state"] != "quit_requested" {
                return Err(invalid());
            }
            Ok(json!({"requested":true,"monitor_epoch":epoch,"state":"quit_requested"}))
        }
        "status" | "set_connections" | "ensure_monitor" => {
            let monitor = &value["monitor"];
            let state = monitor["state"]
                .as_str()
                .filter(|s| ["running", "stopped"].contains(s))
                .ok_or_else(invalid)?;
            let epoch = nullable_hex(&monitor["epoch"], 32)?;
            let controllable = monitor["controllable"].as_bool().ok_or_else(invalid)?;
            if controllable && (state != "running" || epoch.is_none()) {
                return Err(invalid());
            }
            let selection = &value["selection"];
            let revision = selection["revision"]
                .as_str()
                .filter(|s| hex(s, 64))
                .ok_or_else(invalid)?;
            let applied = nullable_hex(&selection["applied_revision"], 64)?;
            let connections = selection["connections"]
                .as_array()
                .filter(|a| a.len() <= 1000)
                .ok_or_else(invalid)?;
            if connections
                .iter()
                .any(|v| !v.as_str().is_some_and(|s| identifier(s, 128)))
            {
                return Err(invalid());
            }
            let readiness = &value["readiness"];
            let readiness_state = readiness["state"]
                .as_str()
                .filter(|s| ["fresh", "stale", "unavailable"].contains(s))
                .ok_or_else(invalid)?;
            let hosts = readiness["hosts"]
                .as_array()
                .filter(|a| a.len() <= 1000)
                .ok_or_else(invalid)?
                .iter()
                .map(readiness_row)
                .collect::<Result<Vec<_>, _>>()?;
            let connector = if readiness["connector"].is_null() {
                Value::Null
            } else {
                readiness_row(&readiness["connector"])?
            };
            Ok(
                json!({"configuration":configuration(&value["configuration"])? ,"monitor":{"state":state,"epoch":epoch,"controllable":controllable},"selection":{"revision":revision,"connections":connections,"applied_revision":applied},"readiness":{"state":readiness_state,"observed_at":timestamp(&readiness["observed_at"])? ,"hosts":hosts,"connector":connector}}),
            )
        }
        _ => Err(invalid()),
    }
}
fn nullable_hex(value: &Value, len: usize) -> Result<Option<&str>, String> {
    if value.is_null() {
        return Ok(None);
    }
    value
        .as_str()
        .filter(|s| hex(s, len))
        .map(Some)
        .ok_or_else(|| "Invalid Fleet version".into())
}
fn timestamp(value: &Value) -> Result<Option<&str>, String> {
    if value.is_null() {
        return Ok(None);
    }
    value
        .as_str()
        .filter(|s| {
            s.len() <= 40
                && s.bytes()
                    .all(|b| b.is_ascii_digit() || b"-:+.TZ".contains(&b))
        })
        .map(Some)
        .ok_or_else(|| "Invalid Fleet observation time".into())
}
fn configuration(value: &Value) -> Result<Value, String> {
    let valid = value["valid"]
        .as_bool()
        .ok_or("Invalid Fleet configuration result")?;
    let binding = value["binding"]
        .as_str()
        .filter(|s| hex(s, 64))
        .ok_or("Invalid Fleet configuration binding")?;
    let count = value["issues"]
        .as_array()
        .filter(|a| a.len() <= 1000)
        .ok_or("Invalid Fleet configuration issues")?
        .len();
    let connections = value["connections"]
        .as_array()
        .filter(|a| a.len() <= 1000)
        .ok_or("Invalid Fleet connections")?;
    let mut names = HashSet::new();
    let connections = connections
        .iter()
        .map(|entry| {
            let name = entry["name"]
                .as_str()
                .filter(|s| identifier(s, 128))
                .ok_or("Invalid Fleet connection name")?;
            let label = entry["label"]
                .as_str()
                .filter(|s| {
                    s.len() <= 1024 && s.chars().count() <= 256 && !s.chars().any(char::is_control)
                })
                .ok_or("Invalid Fleet connection label")?;
            let kind = entry["kind"]
                .as_str()
                .filter(|s| ["host", "connector"].contains(s))
                .ok_or("Invalid Fleet connection kind")?;
            if !names.insert(name) {
                return Err("Duplicate Fleet connection");
            }
            Ok(json!({"name":name,"label":label,"kind":kind}))
        })
        .collect::<Result<Vec<_>, &str>>()?;
    // The Kit validation report can contain local paths; only its status/count crosses IPC.
    Ok(json!({"valid":valid,"binding":binding,"issue_count":count,"connections":connections}))
}
fn readiness_row(value: &Value) -> Result<Value, String> {
    let invalid = || "Invalid Fleet readiness".to_owned();
    let name = value["name"]
        .as_str()
        .filter(|s| identifier(s, 128))
        .ok_or_else(invalid)?;
    let label = value["label"]
        .as_str()
        .filter(|s| s.len() <= 1024 && s.chars().count() <= 256 && !s.chars().any(char::is_control))
        .ok_or_else(invalid)?;
    let level = value["level"]
        .as_str()
        .filter(|s| ["off", "ready", "degraded", "down"].contains(s))
        .ok_or_else(invalid)?;
    let selected = value["selected"].as_bool().ok_or_else(invalid)?;
    let stale = value["stale"].as_bool().ok_or_else(invalid)?;
    let code = value["code"].as_str().filter(|s| identifier(s, 80));
    let blocking = value["blocking"].as_str().filter(|s| {
        [
            "inventory",
            "tunnel",
            "tls",
            "auth",
            "bat",
            "workspace",
            "connector",
            "contract",
            "stale",
        ]
        .contains(s)
    });
    let mut layers = serde_json::Map::new();
    for key in ["tunnel", "tls", "bat", "workspace"] {
        if let Some(v) = value["layers"][key].as_bool() {
            layers.insert(key.into(), json!(v));
        }
    }
    if let Some(auth) = value["layers"]["auth"]
        .as_str()
        .filter(|s| ["ok", "unknown", "refused"].contains(s))
    {
        layers.insert("auth".into(), json!(auth));
    }
    if let Some(version) = value["layers"]["version"].as_str().filter(|s| {
        !s.is_empty() && s.len() <= 40 && s.bytes().all(|b| b.is_ascii_digit() || b == b'.')
    }) {
        layers.insert("version".into(), json!(version));
    }
    Ok(
        json!({"name":name,"label":label,"level":level,"selected":selected,"stale":stale,"code":code,"blocking":blocking,"observed_at":timestamp(&value["observed_at"])? ,"layers":layers}),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    fn fixture() -> Value {
        serde_json::from_str(include_str!("../../tests/fixtures/fleet-status.json")).unwrap()
    }
    fn contract() -> Value {
        serde_json::from_str(include_str!("../../tests/fixtures/fleet-contract.json")).unwrap()
    }
    fn request(action: &str, id: &str) -> Value {
        json!({"schema_version":1,"request_id":id,"action":action})
    }
    struct Temp(PathBuf);
    impl Temp {
        fn new() -> Self {
            let p = std::env::temp_dir().join(format!(
                "bac-native-fleet-{}-{}",
                std::process::id(),
                REQUEST.fetch_add(1, Ordering::Relaxed)
            ));
            std::fs::create_dir_all(&p).unwrap();
            Self(p)
        }
    }
    impl Drop for Temp {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn ipc_refuses_paths_commands_pids_credentials_and_invalid_selection() {
        for body in [
            json!({"action":"shell","command":"whoami"}),
            json!({"action":"status","kit_root":"C:/other"}),
            json!({"action":"status","token":"secret"}),
            json!({"action":"quit_owned","pid":42}),
        ] {
            assert!(serde_json::from_value::<FleetRequest>(body).is_err());
        }
        let mut body = json!({"action":"set_connections","connections":["node-1"],"expected_configuration_binding":"c".repeat(64),"expected_selection_revision":"d".repeat(64),"expected_monitor_epoch":null});
        assert!(serde_json::from_value::<FleetRequest>(body.clone())
            .unwrap()
            .envelope("test")
            .is_ok());
        for names in [
            json!(["node-1", "node-1"]),
            json!(["../evil"]),
            json!(["node;whoami"]),
            json!(["x".repeat(129)]),
        ] {
            body["connections"] = names;
            assert!(serde_json::from_value::<FleetRequest>(body.clone())
                .unwrap()
                .envelope("test")
                .is_err());
        }
    }
    #[test]
    fn response_identity_schema_and_contract_are_fenced() {
        let req = request("status", "fixture-status");
        let original = fixture();
        assert!(parse_response(&serde_json::to_vec(&original).unwrap(), &req).is_ok());
        for (field, value) in [
            ("request_id", json!("other")),
            ("schema_version", json!(2)),
            ("ok", json!(1)),
        ] {
            let mut doc = original.clone();
            doc[field] = value;
            assert!(parse_response(&serde_json::to_vec(&doc).unwrap(), &req).is_err());
        }
        let mut version = contract();
        assert!(parse_response(
            &serde_json::to_vec(&version).unwrap(),
            &request("contract", "fixture-contract")
        )
        .is_ok());
        version["result"]["supported_actions"] = json!(["status"]);
        assert!(parse_response(
            &serde_json::to_vec(&version).unwrap(),
            &request("contract", "fixture-contract")
        )
        .is_err());
        assert!(parse_response(&vec![b' '; MAX_OUTPUT + 1], &req).is_err());
    }
    #[test]
    fn responses_only_expose_known_fields_and_safe_errors() {
        let mut doc = fixture();
        doc["result"]["token"] = json!("do-not-expose");
        doc["result"]["monitor"]["pid"] = json!(999);
        doc["result"]["configuration"]["issues"] = json!([{"message":"secret-path"}]);
        doc["result"]["readiness"]["hosts"][0]["layers"]["auth"] = json!("Bearer secret");
        let result = parse_response(
            &serde_json::to_vec(&doc).unwrap(),
            &request("status", "fixture-status"),
        )
        .unwrap();
        let text = result.to_string();
        assert!(
            !text.contains("do-not-expose")
                && !text.contains("secret-path")
                && !text.contains("Bearer")
                && !text.contains("\"pid\"")
        );
        assert_eq!(result["configuration"]["issue_count"], 1);
        assert_eq!(
            result["readiness"]["hosts"][1]["layers"]["version"],
            "3.2.5"
        );
        let error = json!({"schema_version":1,"request_id":"error","ok":false,"error":{"code":"fake-secret-token","message":"Bearer secret"}});
        let text = parse_response(
            &serde_json::to_vec(&error).unwrap(),
            &request("status", "error"),
        )
        .unwrap_err();
        assert!(text.contains("INTERNAL") && !text.contains("secret"));
    }
    #[test]
    fn trusted_config_requires_bounded_local_installation_and_contained_adapter() {
        let temp = Temp::new();
        let config = temp.0.join("fleet.json");
        assert!(load_script(&config).is_err());
        let root = temp.0.join("kit");
        std::fs::create_dir_all(root.join("client")).unwrap();
        std::fs::write(root.join("client/fleet-desktop.ps1"), "# fixture").unwrap();
        std::fs::write(
            &config,
            serde_json::to_vec(&json!({"kit_root":root})).unwrap(),
        )
        .unwrap();
        assert!(load_script(&config).is_ok());
        for body in [
            json!({"kit_root":"relative"}),
            json!({"kit_root":root,"executable":"other"}),
            json!({"kit_root":"\\\\server\\share"}),
        ] {
            std::fs::write(&config, serde_json::to_vec(&body).unwrap()).unwrap();
            assert!(load_script(&config).is_err());
        }
        std::fs::write(&config, vec![b' '; 16385]).unwrap();
        assert!(load_script(&config).is_err());
    }
    #[cfg(unix)]
    #[test]
    fn adapter_symlink_cannot_escape_trusted_installation() {
        let temp = Temp::new();
        let root = temp.0.join("kit");
        std::fs::create_dir_all(root.join("client")).unwrap();
        let outside = temp.0.join("outside.ps1");
        std::fs::write(&outside, "# fixture").unwrap();
        std::os::unix::fs::symlink(outside, root.join("client/fleet-desktop.ps1")).unwrap();
        let config = temp.0.join("fleet.json");
        std::fs::write(
            &config,
            serde_json::to_vec(&json!({"kit_root":root})).unwrap(),
        )
        .unwrap();
        assert!(load_script(&config).is_err());
    }
    #[cfg(windows)]
    #[test]
    fn windows_paths_refuse_network_and_device_namespaces() {
        for path in [
            r"\\server\share\kit",
            "//server/share/kit",
            r"\\?\UNC\server\share\kit",
            r"\\.\PhysicalDrive0",
        ] {
            assert!(
                !bat_fleet_core::installation::local_path(Path::new(path)),
                "{path}"
            );
        }
        assert_eq!(
            powershell_path(PathBuf::from(r"\\?\C:\Tools\kit\client\fleet-desktop.ps1")).unwrap(),
            PathBuf::from(r"C:\Tools\kit\client\fleet-desktop.ps1")
        );
    }
    #[cfg(windows)]
    #[tokio::test]
    async fn windows_contract_fixture_uses_actual_system_powershell() {
        let temp = Temp::new();
        let root = temp.0.join("kit with spaces");
        std::fs::create_dir_all(root.join("client")).unwrap();
        std::fs::write(
            root.join("client/fleet-desktop.ps1"),
            include_str!("../../tests/fixtures/fleet-contract.ps1"),
        )
        .unwrap();
        std::fs::write(
            root.join("client/contract.json"),
            include_str!("../../tests/fixtures/fleet-contract.json"),
        )
        .unwrap();
        std::fs::write(
            temp.0.join("fleet.json"),
            serde_json::to_vec(&json!({"kit_root":root})).unwrap(),
        )
        .unwrap();
        let bridge = FleetBridge::load(&temp.0);
        // Synthetic process fixture has no inventory, credentials or mutation implementation.
        let result = bridge.request(FleetRequest::Contract {}).await;
        if result.is_err() {
            // Synthetic diagnostics only: distinguish pipe, console and environment startup.
            // No inventory, credentials or controls are implemented by this script.
            let executable = powershell().unwrap();
            let script = load_script(&bridge.config).unwrap();
            for probe in ["null-input", "console", "windows-environment"] {
                let _ = std::fs::remove_file(root.join("client/phase.txt"));
                let mut command = adapter_command(&executable, &script).unwrap();
                let outcome = if probe == "null-input" {
                    command
                        .stdin(Stdio::null())
                        .stdout(Stdio::null())
                        .stderr(Stdio::null())
                        .kill_on_drop(true);
                    let mut child = command.spawn().unwrap();
                    format!(
                        "{:?}",
                        tokio::time::timeout(Duration::from_secs(5), child.wait()).await
                    )
                } else {
                    if probe == "console" {
                        command.creation_flags(0);
                    } else {
                        for name in [
                            "PSModulePath",
                            "ComSpec",
                            "OS",
                            "PATHEXT",
                            "PROCESSOR_ARCHITECTURE",
                            "NUMBER_OF_PROCESSORS",
                            "ProgramW6432",
                            "CommonProgramW6432",
                            "ALLUSERSPROFILE",
                        ] {
                            if let Some(value) = std::env::var_os(name) {
                                command.env(name, value);
                            }
                        }
                    }
                    format!(
                        "{:?}",
                        run_command(
                            command,
                            &request("contract", "fixture-diagnostic"),
                            Duration::from_secs(5)
                        )
                        .await
                        .map(|_| ())
                    )
                };
                let phase = std::fs::read_to_string(root.join("client/phase.txt"))
                    .unwrap_or_else(|_| "not-started".into());
                eprintln!("synthetic startup probe {probe}: {outcome}; phase: {phase}");
            }
        }
        let result = result.unwrap();
        assert_eq!(result["implementation_version"], "desktop-facade-v1");
    }
    #[cfg(unix)]
    fn python(code: &str) -> Command {
        let mut c = Command::new("python3");
        c.args(["-c", code]);
        c
    }
    #[cfg(unix)]
    #[tokio::test]
    async fn transport_closes_stdin_bounds_stdout_and_does_not_trust_exit_status_alone() {
        let req = request("status", "fixture-status");
        let echo="import sys,json; r=json.load(sys.stdin); print(json.dumps(dict(schema_version=1,request_id=r['request_id'],ok=True,result={})))";
        let bytes = run_command(python(echo), &req, Duration::from_secs(5))
            .await
            .unwrap();
        assert_eq!(
            serde_json::from_slice::<Value>(&bytes).unwrap()["request_id"],
            "fixture-status"
        );
        assert!(run_command(
            python(
                "import sys; sys.stdin.read(); sys.stdout.write('x'*262145); sys.stdout.flush()"
            ),
            &req,
            Duration::from_secs(5)
        )
        .await
        .unwrap_err()
        .contains("bound"));
        assert!(run_command(
            python("import sys;sys.stdin.read();print('{\"ok\":true}');sys.exit(1)"),
            &req,
            Duration::from_secs(5)
        )
        .await
        .unwrap_err()
        .contains("unknown"));
        assert!(run_command(
            python("print('should not run')"),
            &json!({"payload":"x".repeat(MAX_INPUT)}),
            Duration::from_secs(5)
        )
        .await
        .unwrap_err()
        .contains("bound"));
    }
    #[cfg(target_os = "linux")]
    #[tokio::test]
    async fn timeout_kills_only_the_owned_adapter_and_never_retries() {
        let temp = Temp::new();
        let marker = temp.0.join("started");
        let mut command = python(
            "import os,sys,time; open(sys.argv[1],'w').write(str(os.getpid())); time.sleep(20)",
        );
        command.arg(&marker);
        let error = run_command(
            command,
            &request("ensure_monitor", "test"),
            Duration::from_millis(300),
        )
        .await
        .unwrap_err();
        assert!(error.contains("timed out") && error.contains("read status"));
        let pid = std::fs::read_to_string(&marker).unwrap();
        for _ in 0..50 {
            if !Path::new(&format!("/proc/{pid}")).exists() {
                return;
            }
            tokio::time::sleep(Duration::from_millis(20)).await;
        }
        panic!("owned adapter still exists after timeout");
    }
}
