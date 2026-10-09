//! Native readonly probe adapter. Fixed trusted executable; never PATH/IPC commands.
use crate::{
    inventory::Endpoint,
    route::{tailscale_direct, ProbeFuture, RouteProbe},
    Result,
};
use std::{
    path::{Path, PathBuf},
    process::Stdio,
};
use tokio::{
    io::AsyncReadExt,
    net::TcpStream,
    process::Command,
    time::{timeout_at, Instant},
};
use zeroize::Zeroizing;

pub struct NativeRouteProbe {
    tailscale: Option<PathBuf>,
}
impl NativeRouteProbe {
    /// Path comes from trusted native installation discovery/configuration.
    /// None means not installed; direct is ineligible, with no command lookup.
    pub fn new(tailscale: Option<&Path>) -> Result<Self> {
        let tailscale = tailscale
            .map(|path| {
                if !path.is_absolute() {
                    return Err("ROUTE_EXECUTABLE_INVALID");
                }
                let canonical = path
                    .canonicalize()
                    .map_err(|_| "ROUTE_EXECUTABLE_INVALID")?;
                let expected = if cfg!(windows) {
                    "tailscale.exe"
                } else {
                    "tailscale"
                };
                if !canonical.is_file()
                    || !canonical
                        .file_name()
                        .and_then(|s| s.to_str())
                        .is_some_and(|s| s.eq_ignore_ascii_case(expected))
                {
                    return Err("ROUTE_EXECUTABLE_INVALID");
                }
                #[cfg(windows)]
                {
                    use std::path::{Component, Prefix};
                    // Native installation discovery also excludes mapped drives.
                    if !matches!(canonical.components().next(), Some(Component::Prefix(p))
                        if matches!(p.kind(), Prefix::Disk(_) | Prefix::VerbatimDisk(_)))
                    {
                        return Err("ROUTE_EXECUTABLE_INVALID");
                    }
                }
                Ok(canonical)
            })
            .transpose()?;
        Ok(Self { tailscale })
    }
}
impl RouteProbe for NativeRouteProbe {
    fn tailscale_direct<'a>(&'a self, ip: &'a str, deadline: Instant) -> ProbeFuture<'a> {
        Box::pin(async move {
            let Some(path) = &self.tailscale else {
                return false;
            };
            if Instant::now() >= deadline || !path.is_file() {
                return false;
            }
            let mut command = Command::new(path);
            command
                .args(["status", "--json"])
                .env_clear()
                .stdin(Stdio::null())
                .stdout(Stdio::piped())
                .stderr(Stdio::null())
                .kill_on_drop(true);
            #[cfg(windows)]
            {
                command.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
                for key in ["SystemRoot", "WINDIR"] {
                    if let Some(value) = std::env::var_os(key) {
                        command.env(key, value);
                    }
                }
            }
            let Ok(mut child) = command.spawn() else {
                return false;
            };
            let Some(stdout) = child.stdout.take() else {
                return false;
            };
            let attempt = async {
                let mut bytes = Zeroizing::new(Vec::new());
                if stdout
                    .take(1024 * 1024 + 1)
                    .read_to_end(&mut bytes)
                    .await
                    .is_err()
                    || bytes.len() > 1024 * 1024
                {
                    return false;
                }
                let Ok(status) = child.wait().await else {
                    return false;
                };
                status.success() && tailscale_direct(&bytes, ip)
            };
            // On timeout/cancellation/error before wait completes, dropping child
            // requests termination through its retained OS process object only.
            timeout_at(deadline, attempt).await.unwrap_or(false) && Instant::now() < deadline
        })
    }
    fn tcp<'a>(&'a self, endpoint: &'a Endpoint, deadline: Instant) -> ProbeFuture<'a> {
        Box::pin(async move {
            if Instant::now() >= deadline {
                return false;
            }
            matches!(
                timeout_at(
                    deadline,
                    TcpStream::connect((endpoint.address.as_str(), endpoint.port))
                )
                .await,
                Ok(Ok(_))
            ) && Instant::now() < deadline
        })
    }
}
