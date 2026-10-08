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
        let mut response = request
            .send()
            .await
            .map_err(|_| "Central request did not complete; retry uses the same operation key")?;
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
            r"sessions/[A-Za-z0-9_.-]+/[A-Za-z0-9_.:-]+(?:/(?:messages|checkpoint-preview|history|relations))?|",
            r"operations/op_[0-9a-f]{32}|tasks/[0-9a-f-]{8,64}(?:/(?:history|sessions))?|checkpoints/cp_[0-9a-f]{32}|",
            r"hosts/[A-Za-z0-9_.-]+/discovery|worktrees/wt_[0-9a-f]{32}(?:/(?:history|relations))?|",
            r"projects/prj_[0-9a-f]{20}|work-items/wi_[0-9a-f]{20}|repositories/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pulls/[0-9]{1,9}|",
            r"delivery/previews/mpv_[0-9a-f]{32}|integrations/previews/ipv_[0-9a-f]{32}|integrations/op_[0-9a-f]{32})$")).unwrap())
    } else if input.method == "POST" {
        POST.get_or_init(|| {
            Regex::new(r"^/operations(?:/op_[0-9a-f]{32}/(?:cancel|resume))?$").unwrap()
        })
    } else {
        return Err("Only defined central GET and operation POST requests are allowed".into());
    };
    if !pattern.is_match(path) {
        return Err("Central route is not allowed".into());
    }
    for (key, value) in url::form_urlencoded::parse(query.as_bytes()) {
        if key.chars().chain(value.chars()).any(char::is_control) {
            return Err("Control characters in central query are refused".into());
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
                | "checkpoint"
                | "project_id"
                | "state"
                | "live"
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
