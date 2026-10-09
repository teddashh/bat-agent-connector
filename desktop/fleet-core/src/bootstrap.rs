//! Opt-in fixed Connector cold bootstrap, not central operations or readiness.
//! Native-only recipe/config/selection and one durable local ensure fence.
use crate::{
    configuration::Configuration, digest, migration_io as files, ownership::ProbeGeneration,
    strict_json, Result,
};
use serde::{Deserialize, Serialize};
use std::{
    future::Future,
    path::{Path, PathBuf},
    pin::Pin,
    time::Duration,
};
use tokio::time::{timeout_at, Instant};

const LIMIT: usize = 16384;
const MAX_QUERIES: u8 = 4;
pub const RECIPE_FILE: &str = "fleet-connector-bootstrap.json";
pub const RECEIPT_FILE: &str = "bat-fleet-connector-bootstrap.json";
pub const HELPER_COMMAND: &str = "/usr/local/libexec/bat-connector-bootstrap-v1";
fn hex(s: &str, n: usize) -> bool {
    s.len() == n
        && s.bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}
fn literal(s: &str) -> bool {
    !s.is_empty()
        && s.len() <= 128
        && s.bytes()
            .all(|c| c.is_ascii_alphanumeric() || b"_.-".contains(&c))
        && s.as_bytes()[0].is_ascii_alphanumeric()
}
fn remote_path(s: &str) -> bool {
    s.starts_with('/')
        && s.len() <= 4096
        && s[1..].split('/').all(|c| {
            !c.is_empty()
                && c != "."
                && c != ".."
                && c.bytes()
                    .all(|c| c.is_ascii_alphanumeric() || b"_.-".contains(&c))
        })
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Definition {
    schema_version: u32,
    allow_ensure: bool,
    #[serde(default)]
    auto_ensure: bool,
    ssh_alias: String,
    service_id: String,
    state_directory: String,
    journal_path: String,
    owner_uid: u32,
    server_recipe_sha256: String,
}
/// No Debug/Serialize: contains trusted private deployment paths, never an IPC DTO.
pub struct Recipe {
    definition: Definition,
    path: PathBuf,
    bytes: Vec<u8>,
    binding: String,
    configuration: String,
}
impl Recipe {
    pub fn load(client_root: &Path, configuration: &Configuration) -> Result<Option<Self>> {
        configuration.verify_current()?;
        if !client_root.is_absolute() {
            return Err("BOOTSTRAP_RECIPE_INVALID");
        }
        let path = client_root.join(RECIPE_FILE);
        let Some(bytes) = files::read(&path, LIMIT).map_err(|_| "BOOTSTRAP_RECIPE_INVALID")? else {
            return Ok(None);
        };
        let definition: Definition = serde_json::from_value(strict_json::parse(&bytes, LIMIT)?)
            .map_err(|_| "BOOTSTRAP_RECIPE_INVALID")?;
        if definition.schema_version != 1
            || !literal(&definition.ssh_alias)
            || !literal(&definition.service_id)
            || definition.service_id.len() > 64
            || !remote_path(&definition.state_directory)
            || !remote_path(&definition.journal_path)
            || Path::new(&definition.journal_path).parent()
                != Some(Path::new(&definition.state_directory))
            || !hex(&definition.server_recipe_sha256, 64)
            || configuration.inventory.connector()["ssh_alias"] != definition.ssh_alias
            || configuration.issues.iter().any(|i| i.host == "connector")
        {
            return Err("BOOTSTRAP_RECIPE_INVALID");
        }
        if !definition.allow_ensure {
            return Ok(None);
        }
        let binding = digest(
            format!(
                "connector-bootstrap-v1\n{}\n{}",
                configuration.binding(),
                digest(&bytes)
            )
            .as_bytes(),
        );
        Ok(Some(Self {
            definition,
            path,
            bytes,
            binding,
            configuration: configuration.binding().into(),
        }))
    }
    pub fn verify_current(&self, configuration: &Configuration) -> Result<()> {
        configuration.verify_current()?;
        if configuration.binding() != self.configuration
            || files::read(&self.path, LIMIT)
                .map_err(|_| "BOOTSTRAP_RECIPE_CHANGED")?
                .as_deref()
                != Some(&self.bytes)
        {
            return Err("BOOTSTRAP_RECIPE_CHANGED");
        }
        Ok(())
    }
    pub fn auto_ensure(&self) -> bool {
        self.definition.auto_ensure
    }
    pub fn binding(&self) -> &str {
        &self.binding
    }
    /// Fixed SSH argv. Configured alias is validated native configuration, never IPC.
    pub fn arguments(&self) -> Vec<String> {
        [
            "-T",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "ConnectTimeout=3",
            "-o",
            "ConnectionAttempts=1",
            "-o",
            "ClearAllForwardings=yes",
            "-o",
            "PermitLocalCommand=no",
            "-o",
            "RequestTTY=no",
            "-o",
            "ForwardAgent=no",
            "-o",
            "ForwardX11=no",
            "-o",
            "RemoteCommand=none",
            "-o",
            "SendEnv=-*",
            &self.definition.ssh_alias,
            HELPER_COMMAND,
        ]
        .map(str::to_owned)
        .to_vec()
    }
    fn request(&self, record: &Record, action: Action) -> Request {
        Request {
            protocol: 1,
            recipe_sha256: self.definition.server_recipe_sha256.clone(),
            service_id: self.definition.service_id.clone(),
            state_directory: self.definition.state_directory.clone(),
            journal_path: self.definition.journal_path.clone(),
            owner_uid: self.definition.owner_uid,
            request_id: record.id.clone(),
            generation: record.generation.clone(),
            attempt: record.queries,
            action,
        }
    }
}
fn generation(value: &ProbeGeneration) -> Result<String> {
    if !hex(&value.epoch, 32)
        || !hex(&value.configuration_binding, 64)
        || !hex(&value.selection_revision, 64)
    {
        return Err("BOOTSTRAP_GENERATION_INVALID");
    }
    Ok(digest(
        format!(
            "{}\n{}\n{}\n{}",
            value.epoch, value.configuration_binding, value.selection_revision, value.generation
        )
        .as_bytes(),
    ))
}
#[derive(Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Action {
    Query,
    Ensure,
}
#[derive(Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Request {
    protocol: u32,
    recipe_sha256: String,
    service_id: String,
    state_directory: String,
    journal_path: String,
    owner_uid: u32,
    request_id: String,
    generation: String,
    attempt: u8,
    action: Action,
}
impl Request {
    fn valid(&self) -> bool {
        self.protocol == 1
            && hex(&self.recipe_sha256, 64)
            && literal(&self.service_id)
            && self.service_id.len() <= 64
            && remote_path(&self.state_directory)
            && remote_path(&self.journal_path)
            && Path::new(&self.journal_path).parent() == Some(Path::new(&self.state_directory))
            && hex(&self.request_id, 32)
            && hex(&self.generation, 64)
            && (1..=MAX_QUERIES).contains(&self.attempt)
    }
    /// Private wire body, no token and never a status/log payload.
    pub fn bytes(&self) -> Result<Vec<u8>> {
        serde_json::to_vec(self).map_err(|_| "BOOTSTRAP_PROTOCOL_INVALID")
    }
    pub fn action(&self) -> Action {
        self.action
    }
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ServiceState {
    Unknown,
    Stopped,
    Transitioning,
    OwnerPresent,
    Running,
}
#[derive(Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
enum Owner {
    Unknown,
    Absent,
    Service,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Response {
    protocol: u32,
    recipe_sha256: String,
    service_id: String,
    state_directory: String,
    journal_path: String,
    owner_uid: u32,
    request_id: String,
    generation: String,
    attempt: u8,
    action: Action,
    state: ServiceState,
    owner: Owner,
    ensure_accepted: bool,
}
impl Response {
    fn parse(raw: &[u8], request: &Request) -> Result<Self> {
        let value: Self = serde_json::from_value(strict_json::parse(raw, LIMIT)?)
            .map_err(|_| "BOOTSTRAP_RESPONSE_UNPROVEN")?;
        let echoed = Request {
            protocol: value.protocol,
            recipe_sha256: value.recipe_sha256.clone(),
            service_id: value.service_id.clone(),
            state_directory: value.state_directory.clone(),
            journal_path: value.journal_path.clone(),
            owner_uid: value.owner_uid,
            request_id: value.request_id.clone(),
            generation: value.generation.clone(),
            attempt: value.attempt,
            action: value.action,
        };
        if !request.valid()
            || echoed != *request
            || value.ensure_accepted && request.action != Action::Ensure
            || value.state == ServiceState::Stopped && value.owner != Owner::Absent
            || value.state == ServiceState::Running && value.owner != Owner::Service
            || value.ensure_accepted && value.state != ServiceState::Transitioning
        {
            return Err("BOOTSTRAP_RESPONSE_UNPROVEN");
        }
        Ok(value)
    }
}
pub type Exchange<'a> = Pin<Box<dyn Future<Output = Result<Vec<u8>>> + 'a>>;
pub trait Platform {
    /// Retained cooperative launcher guard + same current login, selected Connector,
    /// installation/config/recipe and captured generation. Call again before IO.
    fn verify(&self, recipe: &Recipe, generation: &ProbeGeneration) -> Result<()>;
    /// Fixed adapter only. All post-intent failures are uncertain; no resend.
    fn exchange<'a>(
        &'a mut self,
        recipe: &'a Recipe,
        request: &'a Request,
        deadline: Instant,
    ) -> Exchange<'a>;
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Phase {
    Querying,
    EnsureRequested,
    NeedsAttention,
    ServiceRunning,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ExchangeReceipt {
    request: Request,
    response: Option<Response>,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Record {
    id: String,
    recipe: String,
    generation: String,
    queries: u8,
    ensure_requested: bool,
    phase: Phase,
    last_state: Option<ServiceState>,
    ensure_accepted: bool,
    exchanges: Vec<ExchangeReceipt>,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Journal {
    version: u32,
    records: Vec<Record>,
}
#[derive(Clone, Debug, Serialize)]
pub struct Status {
    pub request_id: String,
    pub phase: Phase,
    pub queries: u8,
    pub ensure_requested: bool,
    pub ensure_accepted: bool,
    pub last_state: Option<ServiceState>,
}
impl From<&Record> for Status {
    fn from(r: &Record) -> Self {
        Self {
            request_id: r.id.clone(),
            phase: r.phase,
            queries: r.queries,
            ensure_requested: r.ensure_requested,
            ensure_accepted: r.ensure_accepted,
            last_state: r.last_state,
        }
    }
}
/// Safe local receipt identity; no raw recipe paths or wire messages.
#[derive(Clone, Serialize)]
pub struct SavedStatus {
    pub recipe_binding: String,
    pub status: Status,
}
impl From<&Record> for SavedStatus {
    fn from(record: &Record) -> Self {
        Self {
            recipe_binding: record.recipe.clone(),
            status: record.into(),
        }
    }
}
pub struct Store {
    path: PathBuf,
}
impl Store {
    /// Fixed account roaming directory supplied by native code; never IPC.
    pub fn new(roaming: &Path) -> Result<Self> {
        if !roaming.is_absolute() {
            return Err("BOOTSTRAP_RECEIPT_INVALID");
        }
        Ok(Self {
            path: roaming.join(RECEIPT_FILE),
        })
    }
    fn load(&self) -> Result<(Option<Vec<u8>>, Journal)> {
        let raw = files::read(&self.path, 262144).map_err(|_| "BOOTSTRAP_RECEIPT_UNPROVEN")?;
        let journal = if let Some(raw) = &raw {
            let j: Journal = serde_json::from_value(strict_json::parse(raw, 262144)?)
                .map_err(|_| "BOOTSTRAP_RECEIPT_UNPROVEN")?;
            let mut ids = std::collections::HashSet::new();
            if j.version != 1
                || j.records.is_empty()
                || j.records.len() > 64
                || j.records.iter().any(|r| {
                    !ids.insert(&r.id)
                        || !hex(&r.id, 32)
                        || !hex(&r.recipe, 64)
                        || !hex(&r.generation, 64)
                        || r.queries > MAX_QUERIES
                        || r.ensure_accepted && !r.ensure_requested
                        || r.phase == Phase::EnsureRequested && !r.ensure_requested
                        || r.exchanges.len()
                            != usize::from(r.queries) + usize::from(r.ensure_requested)
                        || r.exchanges
                            .iter()
                            .filter(|e| e.request.action == Action::Ensure)
                            .count()
                            != usize::from(r.ensure_requested)
                        || r.exchanges.iter().any(|e| {
                            !e.request.valid()
                                || e.request.request_id != r.id
                                || !hex(&e.request.generation, 64)
                                || !hex(&e.request.recipe_sha256, 64)
                                || e.request.attempt == 0
                                || e.request.attempt > r.queries
                                || e.response.as_ref().is_some_and(|response| {
                                    serde_json::to_vec(response).ok().is_none_or(|raw| {
                                        Response::parse(&raw, &e.request).is_err()
                                    })
                                })
                        })
                        || r.phase == Phase::ServiceRunning
                            && !r.exchanges.iter().any(|e| {
                                e.response
                                    .as_ref()
                                    .is_some_and(|p| p.state == ServiceState::Running)
                            })
                })
            {
                return Err("BOOTSTRAP_RECEIPT_UNPROVEN");
            }
            j
        } else {
            Journal {
                version: 1,
                records: vec![],
            }
        };
        Ok((raw, journal))
    }
    fn save(&self, prior: &mut Option<Vec<u8>>, journal: &Journal) -> Result<()> {
        let next = serde_json::to_vec(journal).map_err(|_| "BOOTSTRAP_RECEIPT_UNPROVEN")?;
        files::replace(&self.path, prior.as_deref(), Some(&next), 262144)
            .map_err(|_| "BOOTSTRAP_RECEIPT_UNPROVEN")?;
        *prior = Some(next);
        Ok(())
    }
    /// Local read only, including after a recipe disappears or its bytes change.
    pub fn latest(&self) -> Result<Option<SavedStatus>> {
        Ok(self.load()?.1.records.last().map(Into::into))
    }
    pub fn status(&self, id: &str) -> Result<Option<SavedStatus>> {
        if !hex(id, 32) {
            return Err("BOOTSTRAP_REQUEST_INVALID");
        }
        Ok(self
            .load()?
            .1
            .records
            .iter()
            .find(|record| record.id == id)
            .map(Into::into))
    }
    /// Persist the original native-generated ID before the UI offers ensure.
    /// No transport; an unresolved request cannot be replaced by a different ID.
    pub fn prepare(
        &self,
        recipe: &Recipe,
        current: &ProbeGeneration,
        id: &str,
        platform: &impl Platform,
    ) -> Result<SavedStatus> {
        let (_, journal) = self.admit(recipe, current, id, platform)?;
        Ok(journal
            .records
            .iter()
            .find(|record| record.id == id)
            .unwrap()
            .into())
    }
    fn admit(
        &self,
        recipe: &Recipe,
        current: &ProbeGeneration,
        id: &str,
        platform: &impl Platform,
    ) -> Result<(Option<Vec<u8>>, Journal)> {
        platform.verify(recipe, current)?;
        if current.configuration_binding != recipe.configuration || !hex(id, 32) {
            return Err("BOOTSTRAP_BINDING_CHANGED");
        }
        let stamp = generation(current)?;
        let (mut prior, mut journal) = self.load()?;
        if let Some(found) = journal.records.iter().find(|r| r.id == id) {
            if found.recipe != recipe.binding {
                return Err("BOOTSTRAP_BINDING_CHANGED");
            }
            if found.phase != Phase::ServiceRunning && journal.records.last().unwrap().id != id {
                return Err("BOOTSTRAP_REQUEST_CHANGED");
            }
        } else {
            if journal
                .records
                .last()
                .is_some_and(|r| r.phase != Phase::ServiceRunning)
            {
                return Err("BOOTSTRAP_UNRESOLVED");
            }
            if journal.records.len() == 64 {
                return Err("BOOTSTRAP_RECEIPT_FULL");
            }
            journal.records.push(Record {
                id: id.into(),
                recipe: recipe.binding.clone(),
                generation: stamp,
                queries: 0,
                ensure_requested: false,
                phase: Phase::Querying,
                last_state: None,
                ensure_accepted: false,
                exchanges: vec![],
            });
            self.save(&mut prior, &journal)?;
        }
        Ok((prior, journal))
    }
    /// One bounded attempt. Same key reuses its receipts. A new key cannot clear
    /// an unresolved ensure; terminal positive service evidence remains historical.
    pub async fn advance(
        &self,
        recipe: &Recipe,
        current: &ProbeGeneration,
        id: &str,
        platform: &mut impl Platform,
    ) -> Result<Status> {
        let (mut prior, mut journal) = self.admit(recipe, current, id, platform)?;
        let found = journal
            .records
            .iter()
            .find(|record| record.id == id)
            .unwrap();
        if found.phase == Phase::ServiceRunning {
            return Ok(found.into());
        }
        let stamp = generation(current)?;
        // A restarted native monitor can reconcile the same recipe under a fresh
        // selected generation, but never send its saved ensure a second time.
        journal.records.last_mut().unwrap().generation = stamp;
        let deadline = Instant::now() + Duration::from_secs(20);
        loop {
            let r = journal.records.last_mut().unwrap();
            if r.queries == MAX_QUERIES || Instant::now() >= deadline {
                r.phase = Phase::NeedsAttention;
                self.save(&mut prior, &journal)?;
                return Ok(journal.records.last().unwrap().into());
            }
            platform.verify(recipe, current)?;
            r.queries += 1;
            let request = recipe.request(r, Action::Query);
            r.exchanges.push(ExchangeReceipt {
                request: request.clone(),
                response: None,
            });
            self.save(&mut prior, &journal)?; // Exact request/count before query, including crashes.
            let raw = timeout_at(deadline, platform.exchange(recipe, &request, deadline)).await;
            let response = match raw {
                Ok(Ok(raw)) => Response::parse(&raw, &request).ok(),
                _ => None,
            };
            platform.verify(recipe, current)?;
            let r = journal.records.last_mut().unwrap();
            if let Some(response) = response {
                r.exchanges.last_mut().unwrap().response = Some(response.clone());
                r.last_state = Some(response.state);
                if response.state == ServiceState::Running {
                    r.phase = Phase::ServiceRunning;
                    self.save(&mut prior, &journal)?;
                    return Ok(journal.records.last().unwrap().into());
                }
                if response.state == ServiceState::Stopped && !r.ensure_requested {
                    r.ensure_requested = true;
                    r.phase = Phase::EnsureRequested;
                    let request = recipe.request(r, Action::Ensure);
                    r.exchanges.push(ExchangeReceipt {
                        request: request.clone(),
                        response: None,
                    });
                    self.save(&mut prior, &journal)?; // Exact request and irreversible local send fence.
                    platform.verify(recipe, current)?;
                    let result =
                        timeout_at(deadline, platform.exchange(recipe, &request, deadline)).await;
                    // Receipt may be persisted after drift; no publication under a new generation.
                    if let Ok(Ok(raw)) = result {
                        if let Ok(response) = Response::parse(&raw, &request) {
                            let r = journal.records.last_mut().unwrap();
                            r.exchanges.last_mut().unwrap().response = Some(response.clone());
                            r.ensure_accepted = response.ensure_accepted;
                            r.last_state = Some(response.state);
                            if response.state == ServiceState::Running {
                                r.phase = Phase::ServiceRunning;
                            }
                        }
                    }
                    self.save(&mut prior, &journal)?;
                    platform.verify(recipe, current)?;
                    if journal.records.last().unwrap().phase == Phase::ServiceRunning {
                        return Ok(journal.records.last().unwrap().into());
                    }
                }
            }
            self.save(&mut prior, &journal)?;
            tokio::time::sleep_until((Instant::now() + Duration::from_millis(100)).min(deadline))
                .await;
        }
    }
}
