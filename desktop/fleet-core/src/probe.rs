//! Native-only, readonly Fleet probes. Not wired to IPC or supervisor runtime.
//!
//! Port basis: Kit 2ec4b11, Invoke-BatProbe / Read-ConnectorCapabilities and
//! readiness contracts. Callers resolve each credential from its own configured
//! reference: the desktop mutation credential is never a fallback. An attempt
//! captures ProbeGeneration before IO; revalidate config and selection before
//! publishing. Neither a TCP listener nor successful auth alone is ready.
use crate::{
    inventory,
    ownership::{probe_current, ProbeGeneration},
    probe_wire::{PinnedCertificate, Wire, MESSAGE_LIMIT},
    strict_json,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    net::SocketAddrV4,
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
    time::Duration,
};
use tokio::{
    net::TcpStream,
    time::{timeout, Instant},
};
use zeroize::Zeroizing;

/// Owned credential has no Debug/Serialize implementation. Owned token/auth
/// buffers are zeroed on drop; transport libraries may retain temporary copies.
pub struct ProbeCredential(Zeroizing<String>);
impl ProbeCredential {
    pub fn new(token: String) -> Self {
        Self(Zeroizing::new(token))
    }
    pub(crate) fn new_zeroizing(token: Zeroizing<String>) -> Self {
        Self(token)
    }
    #[cfg(test)]
    pub(crate) fn fixture_value(&self) -> &str {
        &self.0
    }
}

/// Native inventory-derived inputs, never accepted as a WebView request.
pub struct BatProbeConfig {
    pub endpoint: SocketAddrV4,
    pub certificate_pin: String,
    pub remote_profile_id: String,
    pub required_workspace_ids: Vec<String>,
    pub minimum_version: String,
    pub client_info: Value,
}
pub struct ConnectorProbeConfig {
    pub endpoint: SocketAddrV4,
    pub supported_api_versions: Vec<u64>,
    pub minimum_contract_version: String,
    pub required_features: Vec<String>,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Layer {
    Tunnel,
    Tls,
    Auth,
    Bat,
    Workspace,
    Connector,
    Contract,
    Stale,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Authentication {
    Unknown,
    Refused,
    Ok,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ProbeKind {
    Bat,
    Connector,
}
/// Fixed codes/reasons and validated version only; no remote payload, host/path,
/// token, actor, workspace IDs, capabilities lists or exception strings escape.
#[derive(Clone, Debug)]
pub struct ProbeObservation {
    pub generation: ProbeGeneration,
    pub observed_ms: u64,
    pub kind: ProbeKind,
    pub tunnel: bool,
    pub tls: bool,
    pub auth: Authentication,
    pub bat: bool,
    pub workspace: bool,
    pub connector: bool,
    pub version: Option<String>,
    pub code: Option<&'static str>,
    pub blocking: Option<Layer>,
    pub reason: Option<&'static str>,
}
impl ProbeObservation {
    fn new(kind: ProbeKind, generation: ProbeGeneration, observed_ms: u64) -> Self {
        Self {
            generation,
            observed_ms,
            kind,
            tunnel: false,
            tls: false,
            auth: Authentication::Unknown,
            bat: false,
            workspace: false,
            connector: false,
            version: None,
            code: None,
            blocking: Some(if kind == ProbeKind::Bat {
                Layer::Tunnel
            } else {
                Layer::Connector
            }),
            reason: None,
        }
    }
    fn fail(&mut self, code: &'static str, reason: &'static str) {
        self.code = Some(code);
        self.reason = Some(reason);
    }
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Level {
    Off,
    Degraded,
    Down,
    Ready,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Readiness {
    pub level: Level,
    pub blocking: Option<Layer>,
    pub code: Option<&'static str>,
}
impl Readiness {
    fn new(level: Level, blocking: Option<Layer>, code: Option<&'static str>) -> Self {
        Self {
            level,
            blocking,
            code,
        }
    }
}
/// Caller supplies the current generation, not the captured one relabelled with
/// today's configuration. Clock rollback/future observations fail closed too.
pub fn readiness(
    selected: bool,
    kind: ProbeKind,
    probe: Option<&ProbeObservation>,
    current: &ProbeGeneration,
    now_ms: u64,
) -> Readiness {
    if !selected {
        return Readiness::new(Level::Off, None, None);
    }
    let pending = if kind == ProbeKind::Bat {
        Layer::Bat
    } else {
        Layer::Connector
    };
    let Some(probe) = probe else {
        return Readiness::new(Level::Degraded, Some(pending), Some("PROBE_PENDING"));
    };
    if probe.kind != kind || !probe_current(&probe.generation, current, probe.observed_ms, now_ms) {
        return Readiness::new(Level::Degraded, Some(Layer::Stale), Some("PROBE_STALE"));
    }
    if let Some(code) = probe.code {
        let degraded = [
            "PROBE_TIMEOUT",
            "PROBE_PENDING",
            "CONNECTOR_CONTRACT_UNSUPPORTED",
        ]
        .contains(&code);
        return Readiness::new(
            if degraded {
                Level::Degraded
            } else {
                Level::Down
            },
            probe.blocking,
            Some(code),
        );
    }
    if !probe.tunnel {
        return Readiness::new(Level::Down, Some(Layer::Tunnel), Some("TUNNEL_DOWN"));
    }
    let missing = if kind == ProbeKind::Bat {
        if !probe.tls {
            Some(Layer::Tls)
        } else if probe.auth != Authentication::Ok {
            Some(Layer::Auth)
        } else if !probe.bat {
            Some(Layer::Bat)
        } else if !probe.workspace {
            Some(Layer::Workspace)
        } else {
            None
        }
    } else if !probe.connector {
        Some(Layer::Connector)
    } else {
        None
    };
    match missing {
        Some(layer) => Readiness::new(Level::Degraded, Some(layer), Some("PROBE_PENDING")),
        None => Readiness::new(Level::Ready, None, None),
    }
}
#[derive(Default, Debug, PartialEq, Eq, Serialize)]
pub struct TraySummary {
    pub up: usize,
    pub total: usize,
    pub down: usize,
    pub warn: usize,
}
pub fn tray_summary<'a>(readiness: impl IntoIterator<Item = &'a Readiness>) -> TraySummary {
    let mut summary = TraySummary::default();
    for item in readiness {
        match item.level {
            Level::Off => continue,
            Level::Ready => summary.up += 1,
            Level::Down => summary.down += 1,
            Level::Degraded => summary.warn += 1,
        }
        summary.total += 1;
    }
    summary
}
fn endpoint_valid(endpoint: &SocketAddrV4) -> bool {
    endpoint.ip().is_loopback() && endpoint.port() != 0
}
fn budget_valid(budget: Duration) -> bool {
    !budget.is_zero() && budget <= Duration::from_secs(30)
}
fn id() -> String {
    rand::random::<[u8; 16]>()
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect()
}
fn message(bytes: &[u8]) -> Result<Value, &'static str> {
    let value = strict_json::parse(bytes, MESSAGE_LIMIT).map_err(|_| "message_json")?;
    if !value.is_object() {
        return Err("message_shape");
    }
    Ok(value)
}

/// Default caller budget is 5 seconds (Kit). One deadline covers connect, TLS,
/// HTTP upgrade, auth, workspace load, fragments and ping replies. Cancelling the
/// future drops the owned socket; no background retry/task outlives the attempt.
pub async fn bat_probe(
    config: &BatProbeConfig,
    credential: ProbeCredential,
    generation: ProbeGeneration,
    observed_ms: u64,
    budget: Duration,
) -> ProbeObservation {
    let mut out = ProbeObservation::new(ProbeKind::Bat, generation, observed_ms);
    if !endpoint_valid(&config.endpoint) || !budget_valid(budget) {
        out.fail("INVENTORY_INVALID", "probe_configuration");
        return out;
    }
    let mismatch = Arc::new(AtomicBool::new(false));
    let result = timeout(
        budget,
        bat_attempt(config, &credential, &mut out, mismatch.clone()),
    )
    .await;
    match result {
        Err(_) | Ok(Err("connect_timeout")) => out.fail("PROBE_TIMEOUT", "probe_deadline"),
        Ok(Err(reason)) => {
            let code = if mismatch.load(Ordering::Relaxed) {
                "TLS_IDENTITY_MISMATCH"
            } else if !out.tunnel {
                "TUNNEL_DOWN"
            } else if out.blocking == Some(Layer::Tls) {
                "TLS_FAILED"
            } else {
                "BAT_PROTOCOL_INVALID"
            };
            out.fail(code, reason);
        }
        Ok(Ok(())) => (),
    }
    out
}
async fn bat_attempt(
    config: &BatProbeConfig,
    credential: &ProbeCredential,
    out: &mut ProbeObservation,
    mismatch: Arc<AtomicBool>,
) -> Result<(), &'static str> {
    let tcp = timeout(
        Duration::from_millis(600),
        TcpStream::connect(config.endpoint),
    )
    .await
    .map_err(|_| "connect_timeout")?
    .map_err(|_| "connect_failed")?;
    out.tunnel = true;
    out.blocking = Some(Layer::Tls);
    let Some(pin) = inventory::pin(&config.certificate_pin) else {
        out.fail("TLS_PIN_MISSING", "pin_missing");
        return Ok(());
    };
    let provider = Arc::new(rustls::crypto::ring::default_provider());
    let verifier = Arc::new(PinnedCertificate {
        pin,
        mismatch,
        provider: provider.clone(),
    });
    let tls = rustls::ClientConfig::builder_with_provider(provider)
        .with_protocol_versions(&[&rustls::version::TLS12])
        .map_err(|_| "tls_configuration")?
        .dangerous()
        .with_custom_certificate_verifier(verifier)
        .with_no_client_auth();
    let stream = tokio_rustls::TlsConnector::from(Arc::new(tls))
        .connect("localhost".try_into().unwrap(), tcp)
        .await
        .map_err(|_| "tls_handshake")?;
    out.tls = true;
    out.blocking = Some(Layer::Bat);
    let mut wire = Wire(stream);
    wire.upgrade(&config.endpoint.to_string()).await?;
    out.blocking = Some(Layer::Auth);
    if credential.0.is_empty() {
        out.fail("CREDENTIAL_MISSING", "credential_missing");
        return Ok(());
    }
    let auth_id = id();
    // Serialize a borrowed token, avoiding an extra token-owning serde Value.
    #[derive(Serialize)]
    #[serde(rename_all = "camelCase")]
    struct Auth<'a> {
        r#type: &'a str,
        id: &'a str,
        token: &'a str,
        protocols: [&'a str; 1],
        compression: [&'a str; 1],
        client_info: &'a Value,
    }
    let auth = Zeroizing::new(
        serde_json::to_vec(&Auth {
            r#type: "auth",
            id: &auth_id,
            token: &credential.0,
            protocols: ["bat-remote/v2"],
            compression: ["none"],
            client_info: &config.client_info,
        })
        .map_err(|_| "auth_encoding")?,
    );
    wire.send_text(&auth).await?;
    drop(auth);
    let mut reply = None;
    for _ in 0..100 {
        let value = message(&wire.read_text().await?)?;
        if value["type"] == "auth-result" && value["id"] == auth_id {
            reply = Some(value);
            break;
        }
    }
    let Some(reply) = reply else {
        out.fail("BAT_PROTOCOL_INVALID", "auth_reply_limit");
        return Ok(());
    };
    if reply
        .get("error")
        .is_some_and(|v| !v.is_null() && v != &Value::Bool(false) && v != "")
        || reply["result"] == false
    {
        out.auth = Authentication::Refused;
        out.fail("BAT_AUTH_REFUSED", "auth_refused");
        return Ok(());
    }
    if reply["result"] != true {
        out.fail("BAT_PROTOCOL_INVALID", "auth_result");
        return Ok(());
    }
    out.auth = Authentication::Ok;
    out.blocking = Some(Layer::Bat);
    let version = reply["serverVersion"].as_str().and_then(inventory::version);
    if reply["protocol"] != "bat-remote/v2" || reply["compression"] != "none" || version.is_none() {
        out.fail("BAT_PROTOCOL_INVALID", "bat_negotiation");
        return Ok(());
    }
    // Project normalized numeric components, never arbitrarily long zero-padded
    // remote text. The validated vector also preserves Kit's 3/4-part ordering.
    out.version = Some(
        version
            .as_ref()
            .unwrap()
            .iter()
            .map(u32::to_string)
            .collect::<Vec<_>>()
            .join("."),
    );
    if !inventory::version(&config.minimum_version)
        .is_some_and(|floor| version.as_ref().unwrap() >= &floor)
    {
        out.fail("BAT_VERSION_UNSUPPORTED", "bat_version");
        return Ok(());
    }
    out.bat = true;
    out.blocking = Some(Layer::Workspace);
    let request_id = id();
    wire.send_text(&serde_json::to_vec(&json!({"type":"invoke", "id":request_id, "channel":"workspace:load", "params":{"profileId":config.remote_profile_id}})).map_err(|_| "request_encoding")?).await?;
    for _ in 0..100 {
        let value = message(&wire.read_text().await?)?;
        if value["id"] != request_id {
            continue;
        }
        if value["type"] == "invoke-error" {
            out.fail("WORKSPACE_UNREADABLE", "workspace_refused");
            return Ok(());
        }
        let Some(document) = value["result"]
            .as_str()
            .filter(|_| value["type"] == "invoke-result")
        else {
            out.fail("WORKSPACE_INVALID", "workspace_result");
            return Ok(());
        };
        let Ok(document) = strict_json::parse(document.as_bytes(), MESSAGE_LIMIT) else {
            out.fail("WORKSPACE_INVALID", "workspace_json");
            return Ok(());
        };
        let Some(workspaces) = document.get("workspaces").and_then(Value::as_array) else {
            out.fail("WORKSPACE_INVALID", "workspace_shape");
            return Ok(());
        };
        if config.required_workspace_ids.iter().any(|id| {
            workspaces
                .iter()
                .filter(|ws| ws.get("id").and_then(Value::as_str) == Some(id))
                .count()
                != 1
        }) {
            out.fail("WORKSPACE_BINDING_MISMATCH", "workspace_binding");
            return Ok(());
        }
        out.workspace = true;
        out.blocking = None;
        return Ok(());
    }
    out.fail("BAT_PROTOCOL_INVALID", "workspace_reply_limit");
    Ok(())
}

/// Default caller budget is 2 seconds (Kit). Only the fixed loopback capabilities
/// GET is allowed; redirect/proxy/cookie/retry mechanisms cannot send this token
/// to another endpoint. Results retain no remote host, action or actor records.
pub async fn connector_probe(
    config: &ConnectorProbeConfig,
    credential: ProbeCredential,
    generation: ProbeGeneration,
    observed_ms: u64,
    budget: Duration,
) -> ProbeObservation {
    let mut out = ProbeObservation::new(ProbeKind::Connector, generation, observed_ms);
    if !endpoint_valid(&config.endpoint) || !budget_valid(budget) {
        out.fail("INVENTORY_INVALID", "probe_configuration");
        return out;
    }
    if credential.0.is_empty() {
        out.blocking = Some(Layer::Auth);
        out.fail("CREDENTIAL_MISSING", "credential_missing");
        return out;
    }
    let result = timeout(
        budget,
        connector_attempt(config, &credential, &mut out, budget),
    )
    .await;
    match result {
        Err(_) | Ok(Err("http_timeout")) => out.fail("PROBE_TIMEOUT", "probe_deadline"),
        Ok(Err(reason)) => out.fail("CONNECTOR_UNAVAILABLE", reason),
        Ok(Ok(())) => (),
    }
    out
}
async fn connector_attempt(
    config: &ConnectorProbeConfig,
    credential: &ProbeCredential,
    out: &mut ProbeObservation,
    budget: Duration,
) -> Result<(), &'static str> {
    let client = reqwest::Client::builder()
        .no_proxy()
        .redirect(reqwest::redirect::Policy::none())
        .retry(reqwest::retry::never())
        .connect_timeout(budget.min(Duration::from_millis(600)))
        .build()
        .map_err(|_| "http_configuration")?;
    let mut auth = reqwest::header::HeaderValue::from_str(&Zeroizing::new(format!(
        "Bearer {}",
        *credential.0
    )))
    .map_err(|_| "credential_invalid")?;
    auth.set_sensitive(true);
    let deadline = Instant::now() + budget;
    let mut response = client
        .get(format!("http://{}/api/v1/capabilities", config.endpoint))
        .header(reqwest::header::AUTHORIZATION, auth)
        .send()
        .await
        .map_err(|error| {
            if error.is_timeout() {
                "http_timeout"
            } else {
                "http_unavailable"
            }
        })?;
    out.tunnel = true;
    match response.status().as_u16() {
        401 => {
            out.auth = Authentication::Refused;
            out.blocking = Some(Layer::Auth);
            out.fail("CONNECTOR_AUTH_REFUSED", "auth_refused");
            return Ok(());
        }
        403 => {
            out.blocking = Some(Layer::Auth);
            out.fail("CONNECTOR_SCOPE_MISSING", "observe_required");
            return Ok(());
        }
        200 => (),
        _ => return Err("http_status"),
    }
    if response
        .content_length()
        .is_some_and(|len| len > 1024 * 1024)
    {
        return Err("http_body_bound");
    }
    let mut bytes = Zeroizing::new(Vec::new());
    while let Some(chunk) = response.chunk().await.map_err(|_| "http_body")? {
        if bytes.len() + chunk.len() > 1024 * 1024 {
            return Err("http_body_bound");
        }
        bytes.extend_from_slice(&chunk);
        if Instant::now() >= deadline {
            out.fail("PROBE_TIMEOUT", "probe_deadline");
            return Ok(());
        }
    }
    let value = strict_json::parse(&bytes, 1024 * 1024).map_err(|_| "capabilities_json")?;
    if !value.is_object() {
        return Err("capabilities_shape");
    }
    if !value["hosts"].is_array() || !value["actions"].is_array() {
        out.fail("CONNECTOR_CAPABILITY_MISSING", "capability_shape");
        return Ok(());
    }
    if !value["api_version"]
        .as_u64()
        .is_some_and(|v| config.supported_api_versions.contains(&v))
        || !value["contract_version"].as_str().is_some_and(|v| {
            inventory::contract_date(v)
                && inventory::contract_date(&config.minimum_contract_version)
                && v >= config.minimum_contract_version.as_str()
        })
    {
        out.blocking = Some(Layer::Contract);
        out.fail("CONNECTOR_CONTRACT_UNSUPPORTED", "contract_version");
        return Ok(());
    }
    if value["scopes"] != json!(["observe"]) {
        out.blocking = Some(Layer::Auth);
        out.fail("CONNECTOR_SCOPE_MISSING", "observe_required");
        return Ok(());
    }
    if !value["connector"].as_str().is_some_and(|v| !v.is_empty())
        || !value["features"].is_object()
        || config
            .required_features
            .iter()
            .any(|feature| value["features"].get(feature) != Some(&Value::Bool(true)))
    {
        out.fail("CONNECTOR_CAPABILITY_MISSING", "capability_missing");
        return Ok(());
    }
    out.auth = Authentication::Ok;
    out.connector = true;
    out.blocking = None;
    Ok(())
}
