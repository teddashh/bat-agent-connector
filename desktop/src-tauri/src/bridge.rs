use regex::Regex;
use reqwest::{redirect::Policy, Client, Method};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::{
    path::Path,
    sync::{
        atomic::{AtomicBool, Ordering},
        OnceLock,
    },
    time::Duration,
};
use url::Url;
use zeroize::Zeroizing;

pub const MAX_ARTIFACT_BYTES: usize = 16 * 1024 * 1024;

const MAX_REQUEST: usize = 1024 * 1024;
const MAX_RESPONSE: usize = 8 * 1024 * 1024;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Config {
    pub endpoint: String,
    pub expected_actor: String,
    pub contract_version: String,
}

impl Config {
    pub fn validate(&self) -> Result<Url, String> {
        let url = Url::parse(&self.endpoint).map_err(|_| "Invalid central endpoint")?;
        let loopback = matches!(url.host_str(), Some("127.0.0.1" | "[::1]"));
        if !(url.scheme() == "https" || url.scheme() == "http" && loopback)
            || url.host_str().is_none()
            || !url.username().is_empty()
            || url.password().is_some()
            || url.query().is_some()
            || url.fragment().is_some()
            || url.path() != "/"
        {
            return Err("Endpoint must be an HTTPS origin or a literal loopback HTTP origin, without credentials, path, query or fragment".into());
        }
        if self.expected_actor.trim().is_empty()
            || self.expected_actor.len() > 200
            || self.contract_version != "2026-10-08"
        {
            return Err(
                "Configure expected_actor and the supported contract_version 2026-10-08".into(),
            );
        }
        Ok(url)
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ConnectorRequest {
    pub method: String,
    pub path: String,
    pub body: Option<Value>,
    pub idempotency_key: Option<String>,
}

// Cleanup previews only describe existing central IDs. They cannot carry headers,
// host paths, commands, credential material, or an altered cleanup apply envelope.
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct CleanupPreviewRequest {
    target: CleanupTarget,
    #[serde(default)]
    choices: CleanupChoices,
}

#[derive(Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
enum CleanupTarget {
    Host {
        host: String,
    },
    WorkItem {
        work_item_id: String,
        #[serde(default)]
        include_children: bool,
    },
    Checkpoint {
        checkpoint_id: String,
    },
    Integration {
        operation_id: String,
    },
}

#[derive(Default, Deserialize)]
#[serde(deny_unknown_fields)]
struct CleanupChoices {
    #[serde(default)]
    discard_uncommitted: Vec<String>,
    #[serde(default)]
    release_undelivered: Vec<String>,
}

fn validate_cleanup_preview(body: Option<&Value>) -> Result<(), String> {
    let doc: CleanupPreviewRequest =
        serde_json::from_value(body.cloned().ok_or("Cleanup preview body is required")?)
            .map_err(|_| "Invalid typed cleanup preview request")?;
    let valid_id = match doc.target {
        CleanupTarget::Host { host } => {
            !host.is_empty()
                && host.len() <= 200
                && host
                    .bytes()
                    .all(|b| b.is_ascii_alphanumeric() || b"_.-".contains(&b))
        }
        CleanupTarget::WorkItem {
            work_item_id,
            include_children,
        } => {
            let _ = include_children; // accepted only as the typed boolean for this variant
            Regex::new(r"^wi_[0-9a-f]{20}$")
                .unwrap()
                .is_match(&work_item_id)
        }
        CleanupTarget::Checkpoint { checkpoint_id } => Regex::new(r"^cp_[0-9a-f]{32}$")
            .unwrap()
            .is_match(&checkpoint_id),
        CleanupTarget::Integration { operation_id } => Regex::new(r"^op_[0-9a-f]{32}$")
            .unwrap()
            .is_match(&operation_id),
    };
    let resource = Regex::new(r"^(?:cr|wt)_[0-9a-f]{32}$").unwrap();
    if !valid_id
        || [
            &doc.choices.discard_uncommitted,
            &doc.choices.release_undelivered,
        ]
        .iter()
        .any(|ids| ids.len() > 500 || ids.iter().any(|id| !resource.is_match(id)))
    {
        return Err("Cleanup preview IDs or choice count are invalid".into());
    }
    Ok(())
}

#[derive(Serialize)]
pub struct ConnectorResponse {
    pub status: u16,
    pub data: Value,
}

#[derive(Serialize)]
pub struct NativeStatus {
    pub endpoint: Option<String>,
    pub error: Option<String>,
    pub credential_available: bool,
}

pub struct Bridge {
    config: Option<Config>,
    endpoint: Option<Url>,
    // Never serialized, logged, or returned by an IPC command.
    token: Zeroizing<String>,
    client: Client,
    verified: AtomicBool,
    error: Option<String>,
}

impl Bridge {
    pub fn load(config_dir: &Path, token: Zeroizing<String>) -> Self {
        let result = std::fs::read(config_dir.join("central.json"))
            .map_err(|_| "Create central.json in the app configuration directory".to_owned())
            .and_then(|bytes| {
                if bytes.len() > 16384 {
                    return Err("Central configuration is too large".into());
                }
                serde_json::from_slice::<Config>(&bytes)
                    .map_err(|_| "Invalid central.json configuration".into())
            });
        Self::new(result, token)
    }

    fn new(config: Result<Config, String>, token: Zeroizing<String>) -> Self {
        let (config, endpoint, error) = match config.and_then(|c| c.validate().map(|u| (c, u))) {
            Ok((c, u)) => (Some(c), Some(u), None),
            Err(e) => (None, None, Some(e)),
        };
        Self {
            config,
            endpoint,
            token,
            error,
            verified: AtomicBool::new(false),
            client: Client::builder()
                .redirect(Policy::none())
                .no_proxy()
                .connect_timeout(Duration::from_secs(10))
                .timeout(Duration::from_secs(30))
                .build()
                .expect("native HTTP client"),
        }
    }

    pub fn status(&self) -> NativeStatus {
        NativeStatus {
            endpoint: self.endpoint.as_ref().map(ToString::to_string),
            error: self.error.clone(),
            credential_available: !self.token.is_empty(),
        }
    }

    pub fn disconnect(&self) {
        self.verified.store(false, Ordering::Release);
    }

    pub async fn connect(&self) -> Result<Value, String> {
        self.disconnect();
        let response = self
            .send(&ConnectorRequest {
                method: "GET".into(),
                path: "/capabilities".into(),
                body: None,
                idempotency_key: None,
            })
            .await?;
        if response.status != 200 {
            return Err(format!(
                "Central authentication refused ({})",
                response.status
            ));
        }
        let caps = response.data;
        let config = self
            .config
            .as_ref()
            .ok_or("Central configuration unavailable")?;
        if caps["actor"].as_str() != Some(config.expected_actor.as_str())
            || caps["api_version"].as_u64() != Some(1)
            || caps["contract_version"].as_str() != Some(config.contract_version.as_str())
            || !caps["scopes"]
                .as_array()
                .is_some_and(|s| s.iter().any(|v| v == "observe"))
        {
            return Err(
                "Central identity, API contract, or observe scope does not match configuration"
                    .into(),
            );
        }
        self.verified.store(true, Ordering::Release);
        Ok(caps)
    }

    pub async fn request(&self, input: ConnectorRequest) -> Result<ConnectorResponse, String> {
        validate_request(&input)?;
        if !self.verified.load(Ordering::Acquire) {
            return Err("Connect and verify the configured central identity first".into());
        }
        let response = self.send(&input).await?;
        if response.status == 401 {
            self.disconnect();
        }
        Ok(response)
    }

    pub async fn upload_artifact(
        &self,
        operation_id: &str,
        bytes: &[u8],
    ) -> Result<ConnectorResponse, String> {
        validate_artifact_upload(operation_id, bytes.len())?;
        if !self.verified.load(Ordering::Acquire) {
            return Err("Connect and verify the configured central identity first".into());
        }
        let base = self
            .endpoint
            .as_ref()
            .ok_or("Central configuration unavailable")?;
        let url = base
            .join(&format!("api/v1/artifacts/uploads/{operation_id}/content"))
            .map_err(|_| "Invalid upload operation")?;
        let response = self
            .client
            .post(url)
            .bearer_auth(self.token.as_str())
            .header("Content-Type", "application/octet-stream")
            .body(bytes.to_vec())
            .send()
            .await
            .map_err(|_| "Artifact upload interrupted; retry the original operation")?;
        let response = Self::read_response(response).await?;
        if response.status == 401 {
            self.disconnect();
        }
        Ok(response)
    }

    async fn send(&self, input: &ConnectorRequest) -> Result<ConnectorResponse, String> {
        let base = self
            .endpoint
            .as_ref()
            .ok_or("Central configuration unavailable")?;
        if self.token.is_empty() {
            return Err(
                "Native credential unavailable; set BATC_DESKTOP_TOKEN before launching".into(),
            );
        }
        let url = base
            .join(&format!("api/v1{}", input.path))
            .map_err(|_| "Invalid central route")?;
        let method = Method::from_bytes(input.method.as_bytes()).map_err(|_| "Invalid method")?;
        let mut request = self
            .client
            .request(method, url)
            .bearer_auth(self.token.as_str());
        if let Some(body) = &input.body {
            request = request.json(body);
        }
        if let Some(key) = &input.idempotency_key {
            request = request.header("Idempotency-Key", key);
        }
        let response = request
            .send()
            .await
            .map_err(|_| "Central request did not complete; retry uses the same operation key")?;
        Self::read_response(response).await
    }

    async fn read_response(mut response: reqwest::Response) -> Result<ConnectorResponse, String> {
        let status = response.status().as_u16();
        if (300..400).contains(&status) {
            return Err("Central redirects are refused".into());
        }
        if response
            .content_length()
            .is_some_and(|len| len > MAX_RESPONSE as u64)
        {
            return Err("Central response is too large".into());
        }
        let mut bytes = Vec::new();
        while let Some(chunk) = response
            .chunk()
            .await
            .map_err(|_| "Central response interrupted; outcome may be unknown")?
        {
            if bytes.len() + chunk.len() > MAX_RESPONSE {
                return Err("Central response is too large".into());
            }
            bytes.extend_from_slice(&chunk);
        }
        let data = serde_json::from_slice(&bytes).map_err(|_| "Central response is not JSON")?;
        Ok(ConnectorResponse { status, data })
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct CapturePreviewRequest {
    host: String,
    session_id: String,
    relative_path: String,
}

fn validate_capture_preview(body: Option<&Value>) -> Result<(), String> {
    let doc: CapturePreviewRequest =
        serde_json::from_value(body.cloned().ok_or("Capture preview body is required")?)
            .map_err(|_| "Invalid typed capture preview request")?;
    if doc.host.is_empty()
        || doc.host.len() > 200
        || !doc
            .host
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b"_.-".contains(&b))
        || !(6..=256).contains(&doc.session_id.len())
        || doc.session_id.chars().any(char::is_control)
        || doc.session_id.contains(['/', '\\'])
        || doc.relative_path.is_empty()
        || doc.relative_path.len() > 4096
        || doc.relative_path.contains('\\')
        || doc.relative_path.chars().any(char::is_control)
        || doc
            .relative_path
            .split('/')
            .any(|p| p.is_empty() || p == "." || p == ".." || p.eq_ignore_ascii_case(".git"))
    {
        return Err(
            "Capture requires a host, full session ID and one safe relative file path".into(),
        );
    }
    Ok(())
}

pub fn validate_artifact_upload(operation_id: &str, length: usize) -> Result<(), String> {
    static OPERATION: OnceLock<Regex> = OnceLock::new();
    if length > MAX_ARTIFACT_BYTES
        || !OPERATION
            .get_or_init(|| Regex::new(r"^op_[0-9a-f]{32}$").unwrap())
            .is_match(operation_id)
    {
        return Err("Upload requires an operation ID and at most 16 MiB of bytes".into());
    }
    Ok(())
}

pub fn external_url(input: &str) -> Result<Url, String> {
    let url = Url::parse(input).map_err(|_| "Invalid external URL")?;
    if input.len() > 2048
        || url.scheme() != "https"
        || url.host_str() != Some("github.com")
        || url.port().is_some()
        || !url.username().is_empty()
        || url.password().is_some()
        || url.query().is_some()
    {
        return Err(
            "Only credential-free GitHub HTTPS links can open in the system browser".into(),
        );
    }
    Ok(url)
}

pub fn validate_request(input: &ConnectorRequest) -> Result<(), String> {
    // Match raw paths before URL parsing so traversal cannot be normalized into an allowed route.
    if input.path.len() > 4096
        || input.path.contains(['\\', '#', '\r', '\n'])
        || input.path.chars().any(char::is_control)
    {
        return Err("Invalid central route".into());
    }
    let (path, query) = input.path.split_once('?').unwrap_or((&input.path, ""));
    let mut encoded = query.bytes();
    while let Some(byte) = encoded.next() {
        if byte == b'%'
            && !(encoded.next().is_some_and(|b| b.is_ascii_hexdigit())
                && encoded.next().is_some_and(|b| b.is_ascii_hexdigit()))
        {
            return Err("Malformed central query encoding".into());
        }
    }
    if path.contains('%') || path.split('/').any(|part| part == "." || part == "..") {
        return Err("Encoded or relative central route segments are refused".into());
    }
    static GET: OnceLock<Regex> = OnceLock::new();
    static POST: OnceLock<Regex> = OnceLock::new();
    let pattern = if input.method == "GET" {
        GET.get_or_init(|| Regex::new(concat!(r"^/(?:version|capabilities|bootstrap|hosts|sessions|policy|operations|events|checkpoints|projects|work-items|integrations|integrations/candidates|",
            r"cleanup-retained|cleanup-tombstones(?:/(?:cr|wt)_[0-9a-f]{32})?|artifacts(?:/art_[0-9a-f]{32}/revisions/[1-9][0-9]{0,8})?|",
            r"sessions/[A-Za-z0-9_.-]+/[A-Za-z0-9_.:-]+(?:/(?:messages|checkpoint-preview|history|relations))?|",
            r"operations/op_[0-9a-f]{32}|tasks/[0-9a-f-]{8,64}(?:/(?:history|sessions))?|checkpoints/cp_[0-9a-f]{32}|",
            r"hosts/[A-Za-z0-9_.-]+/discovery|worktrees/wt_[0-9a-f]{32}(?:/(?:history|relations))?|",
            r"projects/prj_[0-9a-f]{20}|work-items/wi_[0-9a-f]{20}|repositories/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pulls/[0-9]{1,9}|",
            r"deployments(?:/(?:preview|dep_[0-9a-f]{32}))?|deployment-environments(?:/history)?|",
            r"delivery/previews/mpv_[0-9a-f]{32}|integrations/previews/ipv_[0-9a-f]{32}|integrations/op_[0-9a-f]{32})$")).unwrap())
    } else if input.method == "POST" {
        POST.get_or_init(|| {
            Regex::new(r"^/(?:artifact-capture-previews|cleanup-previews|operations(?:/op_[0-9a-f]{32}/(?:cancel|resume))?)$")
                .unwrap()
        })
    } else {
        return Err("Only defined central GET and operation POST requests are allowed".into());
    };
    if !pattern.is_match(path) {
        return Err("Central route is not allowed".into());
    }
    if path == "/artifact-capture-previews" {
        if input.path != path || input.idempotency_key.is_some() {
            return Err("Capture preview accepts no query or operation key".into());
        }
        validate_capture_preview(input.body.as_ref())?;
    }
    let cleanup = path.starts_with("/cleanup-");
    let mut query_keys = std::collections::HashSet::new();
    for (key, value) in url::form_urlencoded::parse(query.as_bytes()) {
        if key.chars().chain(value.chars()).any(char::is_control) {
            return Err("Control characters in central query are refused".into());
        }
        if cleanup {
            let allowed = match path {
                "/cleanup-retained" => matches!(
                    key.as_ref(),
                    "host" | "resource_id" | "query" | "cursor" | "limit"
                ),
                "/cleanup-tombstones" => matches!(
                    key.as_ref(),
                    "host" | "kind" | "query" | "original_id" | "work_item_id" | "cursor" | "limit"
                ),
                _ => false,
            };
            if !allowed
                || !query_keys.insert(key.to_string())
                || value.len() > 4096
                || key == "limit" && !value.parse::<u16>().is_ok_and(|n| (1..=200).contains(&n))
            {
                return Err("Cleanup query parameter is invalid".into());
            }
            continue;
        }
        if !matches!(
            key.as_ref(),
            "after"
                | "limit"
                | "cursor"
                | "host"
                | "access"
                | "attention"
                | "status"
                | "pending"
                | "include_archived"
                | "last_n"
                | "method"
                | "from_event"
                | "wait"
                | "resource_type"
                | "resource_id"
                | "session_id"
                | "repository"
                | "recipe"
                | "checkpoint"
                | "project_id"
                | "state"
                | "live"
                | "action"
                | "actor"
                | "before"
                | "discovery"
                | "execution_id"
                | "has_tab"
                | "include_closed"
                | "include_gone"
                | "include_tools"
                | "kind"
                | "lifecycle"
                | "loaded"
                | "max_chars"
                | "offset"
                | "order"
                | "profile_id"
                | "provenance"
                | "provider"
                | "pull_number"
                | "related_resource_id"
                | "related_resource_type"
                | "relation_scope"
                | "since"
                | "stale"
                | "streaming"
                | "until"
                | "work_item_id"
        ) {
            return Err("Central query parameter is not allowed".into());
        }
    }
    if input.method == "GET" && input.body.is_some() {
        return Err("GET requests cannot have a body".into());
    }
    if input
        .body
        .as_ref()
        .is_some_and(|b| b.to_string().len() > MAX_REQUEST)
    {
        return Err("Operation request is too large".into());
    }
    if path == "/cleanup-previews" {
        validate_cleanup_preview(input.body.as_ref())?;
    }
    if let Some(key) = &input.idempotency_key {
        if key.is_empty() || key.len() > 256 || !key.bytes().all(|c| c.is_ascii_graphic()) {
            return Err("Invalid operation idempotency key".into());
        }
    }
    if input.method == "POST" && path == "/operations" && input.idempotency_key.is_none() {
        return Err("Operation creation requires its original idempotency key".into());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        io::{Read, Write},
        net::TcpListener,
        sync::mpsc,
        thread,
    };

    fn request(method: &str, path: &str) -> ConnectorRequest {
        ConnectorRequest {
            method: method.into(),
            path: path.into(),
            body: None,
            idempotency_key: None,
        }
    }
    fn config(endpoint: &str) -> Config {
        Config {
            endpoint: endpoint.into(),
            expected_actor: "fixture-operator".into(),
            contract_version: "2026-10-08".into(),
        }
    }
    fn server(responses: Vec<String>) -> (String, mpsc::Receiver<String>, thread::JoinHandle<()>) {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let endpoint = format!("http://{}/", listener.local_addr().unwrap());
        let (send, receive) = mpsc::channel();
        let handle = thread::spawn(move || {
            for response in responses {
                let (mut socket, _) = listener.accept().unwrap();
                socket
                    .set_read_timeout(Some(Duration::from_secs(3)))
                    .unwrap();
                let mut raw = Vec::new();
                let mut buf = [0; 4096];
                loop {
                    let n = socket.read(&mut buf).unwrap();
                    if n == 0 {
                        break;
                    }
                    raw.extend_from_slice(&buf[..n]);
                    let text = String::from_utf8_lossy(&raw);
                    if let Some((headers, body)) = text.split_once("\r\n\r\n") {
                        let length = headers
                            .lines()
                            .find_map(|l| {
                                l.to_lowercase()
                                    .strip_prefix("content-length: ")
                                    .and_then(|s| s.parse::<usize>().ok())
                            })
                            .unwrap_or(0);
                        if body.len() >= length {
                            break;
                        }
                    }
                }
                let _ = send.send(String::from_utf8(raw).unwrap());
                socket.write_all(response.as_bytes()).unwrap();
            }
        });
        (endpoint, receive, handle)
    }
    fn json_response(body: &str) -> String {
        format!("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}", body.len(), body)
    }
    const CAPS: &str = r#"{"actor":"fixture-operator","api_version":1,"contract_version":"2026-10-08","scopes":["observe","operate"]}"#;

    #[test]
    fn artifact_upload_boundaries_and_read_routes_are_fixed() {
        let operation = format!("op_{}", "a".repeat(32));
        assert!(validate_artifact_upload(&operation, 0).is_ok());
        assert!(validate_artifact_upload(&operation, MAX_ARTIFACT_BYTES).is_ok());
        assert!(validate_artifact_upload(&operation, MAX_ARTIFACT_BYTES + 1).is_err());
        for id in [
            "https://other.example/op",
            "../op_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "op_bad",
            "op_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa?token=x",
        ] {
            assert!(validate_artifact_upload(id, 1).is_err());
        }
        for path in [
            "/artifacts?limit=200",
            "/artifacts/art_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/revisions/1",
        ] {
            assert!(validate_request(&request("GET", path)).is_ok());
        }
        for path in [
            "/artifacts/art_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/revisions/0",
            "/artifacts/art_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/revisions/1/content",
            "/artifacts/uploads/op_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/content",
        ] {
            assert!(validate_request(&request("GET", path)).is_err());
            assert!(validate_request(&request("POST", path)).is_err());
        }
    }

    #[tokio::test]
    async fn artifact_binary_reaches_only_its_operation_bound_central_route() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let endpoint = format!("http://{}/", listener.local_addr().unwrap());
        let (send, receive) = mpsc::channel();
        let worker = thread::spawn(move || {
            for reply in [
                json_response(CAPS),
                json_response(r#"{"operation":{"status":"running"}}"#),
            ] {
                let (mut socket, _) = listener.accept().unwrap();
                socket
                    .set_read_timeout(Some(Duration::from_secs(3)))
                    .unwrap();
                let mut raw = Vec::new();
                let mut buf = [0; 4096];
                loop {
                    let count = socket.read(&mut buf).unwrap();
                    raw.extend_from_slice(&buf[..count]);
                    if let Some(position) = raw.windows(4).position(|part| part == b"\r\n\r\n") {
                        let headers = String::from_utf8_lossy(&raw[..position]);
                        let length = headers
                            .lines()
                            .find_map(|line| {
                                line.to_ascii_lowercase()
                                    .strip_prefix("content-length: ")
                                    .and_then(|n| n.parse::<usize>().ok())
                            })
                            .unwrap_or(0);
                        if raw.len() >= position + 4 + length {
                            break;
                        }
                    }
                    if count == 0 {
                        break;
                    }
                }
                send.send(raw).unwrap();
                socket.write_all(reply.as_bytes()).unwrap();
            }
        });
        let bridge = Bridge::new(
            Ok(config(&endpoint)),
            Zeroizing::new("native-fixture-token".into()),
        );
        bridge.connect().await.unwrap();
        let bytes = [0, 255, 128, 13, 10, 60, 38, 34, 195, 169];
        bridge
            .upload_artifact("op_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", &bytes)
            .await
            .unwrap();
        receive.recv().unwrap();
        let raw = receive.recv().unwrap();
        let split = raw.windows(4).position(|part| part == b"\r\n\r\n").unwrap();
        let headers = String::from_utf8_lossy(&raw[..split]);
        assert!(headers.starts_with(
            "POST /api/v1/artifacts/uploads/op_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/content HTTP/1.1"
        ));
        assert!(headers
            .to_ascii_lowercase()
            .contains("authorization: bearer native-fixture-token"));
        assert!(headers
            .to_ascii_lowercase()
            .contains("content-type: application/octet-stream"));
        assert_eq!(&raw[split + 4..], &bytes);
        worker.join().unwrap();
    }

    #[tokio::test]
    async fn binary_upload_redirect_does_not_forward_credentials() {
        let target = TcpListener::bind("127.0.0.1:0").unwrap();
        target.set_nonblocking(true).unwrap();
        let redirect = format!("HTTP/1.1 307 Temporary Redirect\r\nLocation: http://{}/capture\r\nContent-Length: 0\r\nConnection: close\r\n\r\n", target.local_addr().unwrap());
        let (endpoint, requests, worker) = server(vec![json_response(CAPS), redirect]);
        let bridge = Bridge::new(
            Ok(config(&endpoint)),
            Zeroizing::new("native-fixture-token".into()),
        );
        assert!(bridge
            .upload_artifact("op_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", b"fixture")
            .await
            .is_err());
        bridge.connect().await.unwrap();
        assert!(bridge
            .upload_artifact("op_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", b"fixture")
            .await
            .err()
            .unwrap()
            .contains("redirect"));
        assert!(target.accept().is_err());
        assert_eq!(requests.try_iter().count(), 2);
        worker.join().unwrap();
    }

    #[test]
    fn capture_preview_has_one_fixed_route_and_typed_relative_source() {
        let mut input = request("POST", "/artifact-capture-previews");
        for path in [
            "notes/input.txt",
            "資料/輸入 1.txt",
            "odd/%2e%2e.txt",
            "a:b/file.txt",
        ] {
            input.body = Some(
                serde_json::json!({"host":"demo", "session_id":"session-full-id", "relative_path":path}),
            );
            assert!(validate_request(&input).is_ok(), "{path}");
        }
        for path in [
            "",
            "/etc/passwd",
            "../a",
            "a/../b",
            "a//b",
            "a/",
            ".git/config",
            "a/.GIT/x",
            "a\\b",
            "a\u{0085}b",
        ] {
            input.body = Some(
                serde_json::json!({"host":"demo", "session_id":"session-full-id", "relative_path":path}),
            );
            assert!(validate_request(&input).is_err(), "{path}");
        }
        for body in [
            serde_json::json!({"host":"demo", "session_id":"short", "relative_path":"a"}),
            serde_json::json!({"host":"https://example.invalid", "session_id":"session-1", "relative_path":"a"}),
            serde_json::json!({"host":"demo", "session_id":"session-1", "relative_path":"a", "headers":{"Authorization":"fake"}}),
            serde_json::json!({"host":"demo", "session_id":"session-1", "relative_path":"資料".repeat(1366)}),
            serde_json::json!({"host":"demo", "session_id":"session-1", "relative_path":true}),
        ] {
            input.body = Some(body);
            assert!(validate_request(&input).is_err());
        }
        input.body = Some(
            serde_json::json!({"host":"demo", "session_id":"session-1", "relative_path":"notes.txt"}),
        );
        for path in [
            "/artifact-capture-previews?",
            "/artifact-capture-previews?host=other",
            "/artifact-capture-previews/other",
            "/%61rtifact-capture-previews",
        ] {
            input.path = path.into();
            assert!(validate_request(&input).is_err());
        }
        input.path = "/artifact-capture-previews".into();
        input.idempotency_key = Some("wrong-key".into());
        assert!(validate_request(&input).is_err());
        assert!(validate_request(&request("GET", "/artifact-capture-previews")).is_err());
    }

    #[test]
    fn cleanup_routes_and_typed_previews_are_bounded() {
        let rid = format!("wt_{}", "a".repeat(32));
        for path in [
            format!("/cleanup-tombstones/{rid}"),
            "/cleanup-tombstones?query=old%20place&cursor=&limit=100".into(),
            "/cleanup-retained?host=demo&resource_id=cr_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&cursor="
                .into(),
        ] {
            assert!(validate_request(&request("GET", &path)).is_ok(), "{path}");
        }
        for path in [
            "/cleanup-tombstones/../../../token",
            "/cleanup-tombstones/cr_bad",
            "/cleanup-retained?query=x&query=y",
            "/cleanup-retained?limit=501",
            "/cleanup-retained?limit=true",
            "/cleanup-retained?url=https%3A%2F%2Fevil.example",
            "/cleanup-retained?original_id=x",
            "/cleanup-tombstones?headers=secret",
        ] {
            assert!(validate_request(&request("GET", path)).is_err(), "{path}");
        }
        let mut preview = request("POST", "/cleanup-previews");
        preview.body = Some(serde_json::json!({"target":{"kind":"host","host":"demo"},
            "choices":{"discard_uncommitted":[],"release_undelivered":[rid]}}));
        assert!(validate_request(&preview).is_ok());
        for body in [
            serde_json::json!({"target":{"kind":"host","host":"../other"}}),
            serde_json::json!({"target":{"kind":"host","host":"demo","include_children":true}}),
            serde_json::json!({"target":{"kind":"work_item","work_item_id":"wi_aaaaaaaaaaaaaaaaaaaa","include_children":"true"}}),
            serde_json::json!({"target":{"kind":"host","host":"demo"},"headers":{"Authorization":"fake"}}),
            serde_json::json!({"target":{"kind":"host","host":"demo"},"choices":{"discard_uncommitted":["/tmp/path"]}}),
            serde_json::json!({"target":{"kind":"host","host":"demo"},"choices":{"release_undelivered":vec![rid;501]}}),
        ] {
            preview.body = Some(body);
            assert!(validate_request(&preview).is_err());
        }
        for target in [
            serde_json::json!({"kind":"work_item","work_item_id":"wi_aaaaaaaaaaaaaaaaaaaa","include_children":true}),
            serde_json::json!({"kind":"checkpoint","checkpoint_id":"cp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}),
            serde_json::json!({"kind":"integration","operation_id":"op_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}),
        ] {
            preview.body = Some(serde_json::json!({"target":target}));
            assert!(validate_request(&preview).is_ok());
        }
        preview.path = "/cleanup-previews?wait=3".into();
        assert!(validate_request(&preview).is_err());
        assert!(validate_request(&request("POST", "/cleanup-retained")).is_err());
    }

    #[test]
    fn delivery_reads_are_scoped_to_known_routes() {
        for path in [
            "/deployments/preview?recipe=production",
            "/deployments?recipe=production&limit=5&cursor=page-proof",
            "/deployments/dep_0123456789abcdef0123456789abcdef",
            "/deployment-environments?recipe=production",
            "/deployment-environments/history?recipe=production&limit=5&cursor=page-proof",
        ] {
            assert!(validate_request(&request("GET", path)).is_ok(), "{path}");
            assert!(validate_request(&request("POST", path)).is_err(), "{path}");
        }
        for path in [
            "/deployments/dep_untrusted",
            "/deployments/preview?recipe=prod&url=https://other.example",
            "/deployments/%2e%2e/hosts",
            "/deployments/preview?recipe=prod%0aAuthorization%3Abad",
            "/deployment-environments/history/all",
        ] {
            assert!(validate_request(&request("GET", path)).is_err(), "{path}");
        }
    }

    #[test]
    fn endpoints_require_a_trusted_origin() {
        for endpoint in [
            "https://central.example/",
            "http://127.0.0.1:18796/",
            "http://[::1]:18796/",
        ] {
            assert!(config(endpoint).validate().is_ok(), "{endpoint}");
        }
        for endpoint in [
            "http://central.example/",
            "http://localhost/",
            "file:///tmp/central",
            "https://user:secret@central.example/",
            "https://central.example/path",
            "https://central.example/?token=x",
            "https://central.example/#fragment",
        ] {
            assert!(config(endpoint).validate().is_err(), "{endpoint}");
        }
    }

    #[test]
    fn requests_cannot_escape_the_central_contract() {
        for path in [
            "https://other.example/hosts",
            "//other.example/hosts",
            "/../hosts",
            "/sessions/../hosts",
            "/sessions/%2e%2e/hosts",
            "/hosts#x",
            "/hosts?url=https://other.example",
            "/hosts?token=x",
            "/hosts\\anything",
            "/events/stream",
            "/dashboard/",
            "/shell",
            "/hosts\n",
            "/events?after=%zz",
            "/events?checkpoint=%",
            "/events?checkpoint=%0d%0aAuthorization",
        ] {
            assert!(validate_request(&request("GET", path)).is_err(), "{path}");
        }
        assert!(validate_request(&request("DELETE", "/operations")).is_err());
        assert!(validate_request(&request("POST", "/hosts")).is_err());
        assert!(validate_request(&request("POST", "/operations")).is_err());
        let mut input = request("POST", "/operations?wait=3");
        input.idempotency_key = Some("fixture-key".into());
        input.body = Some(
            serde_json::json!({"action":"session.send", "target":{}, "params":{}, "preconditions":{}}),
        );
        assert!(validate_request(&input).is_ok());
        input.idempotency_key = Some("key\r\nAuthorization: unsafe".into());
        assert!(validate_request(&input).is_err());
        assert!(serde_json::from_value::<ConnectorRequest>(
            serde_json::json!({"method":"GET","path":"/hosts",
            "headers":{"Authorization":"unsafe"}})
        )
        .is_err());
    }

    #[test]
    fn external_navigation_is_https_github_without_credentials() {
        assert!(external_url("https://github.com/example/repository/pull/1").is_ok());
        for value in [
            "file:///tmp/secret",
            "javascript:alert(1)",
            "https://other.example/",
            "https://github.com.evil.example/",
            "https://user:secret@github.com/",
            "https://github.com/?token=secret",
            "http://github.com/",
            "https://github.com:8443/",
        ] {
            assert!(external_url(value).is_err(), "{value}");
        }
    }

    #[test]
    fn observation_routes_allow_stable_paging_and_documented_filters() {
        for path in [
            "/sessions?order=id&include_gone=true&provenance=manual",
            "/sessions/h1/fixture-session/history?order=desc&kind=session.updated&since=1&until=2",
            "/hosts/h1/discovery?after=0&limit=50",
            "/worktrees/wt_00000000000000000000000000000000/relations?include_closed=true&execution_id=fixture-execution",
            "/events?after=1&checkpoint=s1.fixture.signature",
        ] {
            assert!(validate_request(&request("GET", path)).is_ok(), "{path}");
        }
    }

    #[tokio::test]
    async fn contract_mismatch_cannot_unlock_operations() {
        let (endpoint, received, handle) = server(vec![json_response(
            &CAPS.replace("2026-10-08", "unsupported"),
        )]);
        let bridge = Bridge::new(
            Ok(config(&endpoint)),
            Zeroizing::new("fixture-token".into()),
        );
        assert!(bridge.connect().await.is_err());
        assert!(bridge.request(request("GET", "/hosts")).await.is_err());
        assert!(received
            .recv()
            .unwrap()
            .starts_with("GET /api/v1/capabilities "));
        handle.join().unwrap();
    }

    #[tokio::test]
    async fn wrong_identity_cannot_unlock_operations() {
        let (endpoint, received, handle) = server(vec![json_response(
            &CAPS.replace("fixture-operator", "other-actor"),
        )]);
        let bridge = Bridge::new(
            Ok(config(&endpoint)),
            Zeroizing::new("fixture-token".into()),
        );
        assert!(bridge.request(request("GET", "/hosts")).await.is_err());
        assert!(bridge.connect().await.is_err());
        assert!(bridge.request(request("GET", "/hosts")).await.is_err());
        assert!(received
            .recv()
            .unwrap()
            .starts_with("GET /api/v1/capabilities "));
        handle.join().unwrap();
    }

    #[tokio::test]
    async fn native_credentials_and_original_operation_envelope_reach_only_the_fixed_central() {
        let (endpoint, received, handle) = server(vec![
            json_response(CAPS),
            json_response(r#"{"operation":{"operation_id":"op_fixture","status":"accepted"}}"#),
        ]);
        let bridge = Bridge::new(
            Ok(config(&endpoint)),
            Zeroizing::new("fixture-token".into()),
        );
        assert_eq!(bridge.connect().await.unwrap()["actor"], "fixture-operator");
        let body = serde_json::json!({"action":"session.send", "target":{"host":"fixture-host","session_id":"fixture-session"},
            "params":{"text":"fixture message"},"preconditions":{"version":7}});
        let mut input = request("POST", "/operations?wait=3");
        input.idempotency_key = Some("original-key".into());
        input.body = Some(body.clone());
        assert_eq!(
            bridge.request(input).await.unwrap().data["operation"]["status"],
            "accepted"
        );
        let first = received.recv().unwrap();
        let second = received.recv().unwrap();
        assert!(first
            .to_lowercase()
            .contains("authorization: bearer fixture-token"));
        assert!(second
            .to_lowercase()
            .contains("idempotency-key: original-key"));
        assert_eq!(
            serde_json::from_str::<Value>(second.split_once("\r\n\r\n").unwrap().1).unwrap(),
            body
        );
        assert!(!serde_json::to_string(&bridge.status())
            .unwrap()
            .contains("fixture-token"));
        bridge.disconnect();
        assert!(bridge.request(request("GET", "/hosts")).await.is_err());
        handle.join().unwrap();
    }

    #[tokio::test]
    async fn redirects_never_receive_a_second_token_bearing_request() {
        let target = TcpListener::bind("127.0.0.1:0").unwrap();
        target.set_nonblocking(true).unwrap();
        let response = format!("HTTP/1.1 302 Found\r\nLocation: http://{}/steal\r\nContent-Length: 0\r\nConnection: close\r\n\r\n", target.local_addr().unwrap());
        let (endpoint, _, handle) = server(vec![response]);
        let bridge = Bridge::new(
            Ok(config(&endpoint)),
            Zeroizing::new("fixture-token".into()),
        );
        assert!(bridge.connect().await.unwrap_err().contains("redirects"));
        assert!(target.accept().is_err());
        handle.join().unwrap();
    }
}
