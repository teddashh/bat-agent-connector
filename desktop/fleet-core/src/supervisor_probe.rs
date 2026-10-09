//! Readonly probe preparation; credentials remain in Rust-owned worker lifetimes.
use crate::{
    configuration::Configuration,
    credential::{self, CredentialRef},
    inventory,
    ownership::ProbeGeneration,
    probe::{self, BatProbeConfig, ConnectorProbeConfig, ProbeCredential, ProbeObservation},
    Result,
};
use serde_json::Value;
use std::{future::Future, net::SocketAddrV4, path::Path, pin::Pin, time::Duration};

pub type ProbeFuture = Pin<Box<dyn Future<Output = ProbeObservation> + Send>>;
/// Injectable only by trusted native code. It may not fall back to a Dashboard credential.
pub trait ProbeFactory {
    fn credential(
        &self,
        configuration: &Configuration,
        directory: &Path,
        name: &str,
    ) -> Result<ProbeCredential>;
    /// Private source generation. No credential fingerprint or live profile bytes
    /// may enter status/logs. The supervisor repeats this before publication.
    fn source(
        &self,
        configuration: &Configuration,
        _directory: &Path,
        _name: &str,
    ) -> Result<String> {
        Ok(configuration.binding().into())
    }
    fn binding(
        &self,
        configuration: &Configuration,
        directory: &Path,
        name: &str,
        credential: &ProbeCredential,
    ) -> Result<String> {
        Ok(crate::digest(
            format!(
                "{}:{}",
                credential.fingerprint(),
                self.source(configuration, directory, name)?
            )
            .as_bytes(),
        ))
    }
    fn start(
        &self,
        configuration: &Configuration,
        name: &str,
        client_info: &Value,
        credential: ProbeCredential,
        generation: ProbeGeneration,
        now: u64,
    ) -> Result<ProbeFuture>;
}
pub struct NativeProbes;
fn endpoint(value: &Value) -> Result<SocketAddrV4> {
    let ep = inventory::endpoint(value.as_str().ok_or("INVENTORY_INVALID")?, true)?;
    Ok(SocketAddrV4::new(
        ep.address.parse().map_err(|_| "INVENTORY_INVALID")?,
        ep.port,
    ))
}
impl ProbeFactory for NativeProbes {
    fn credential(
        &self,
        configuration: &Configuration,
        directory: &Path,
        name: &str,
    ) -> Result<ProbeCredential> {
        let reference = if name == "connector" {
            CredentialRef::for_connector(&configuration.inventory)?
        } else {
            CredentialRef::for_bat(&configuration.inventory, name)?
        };
        credential::resolve(directory, &reference)
    }
    fn source(
        &self,
        configuration: &Configuration,
        directory: &Path,
        name: &str,
    ) -> Result<String> {
        if name == "connector" {
            return Ok(configuration.binding().into());
        }
        let bytes = credential::read_fixed(directory, "profiles", "index.json", 1048576)
            .map_err(|_| "PROFILE_DRIFT")?;
        // The installed BAT index is mutable application metadata, not the strict
        // configured pair. Bind all bytes, but validate only the selected connection.
        let live = crate::strict_json::parse(
            bytes.strip_prefix(b"\xef\xbb\xbf").unwrap_or(&bytes),
            1048576,
        )
        .map_err(|_| "PROFILE_DRIFT")?;
        let profiles = live
            .get("profiles")
            .and_then(Value::as_array)
            .filter(|p| p.len() <= 10000)
            .ok_or("PROFILE_DRIFT")?;
        let mut seen = std::collections::HashSet::new();
        for profile in profiles {
            let id = profile
                .get("id")
                .and_then(Value::as_str)
                .filter(|id| !id.is_empty() && id.len() <= 256 && !id.contains('\0'))
                .ok_or("PROFILE_DRIFT")?;
            if !seen.insert(id.to_lowercase()) {
                return Err("PROFILE_DRIFT");
            }
        }
        let host = configuration
            .inventory
            .hosts()
            .iter()
            .find(|h| h["name"] == name)
            .ok_or("PROFILE_DRIFT")?;
        let id = host["profile"].as_str().unwrap();
        let original = configuration
            .profile_index
            .profile(id)
            .ok_or("PROFILE_DRIFT")?;
        let actual = profiles
            .iter()
            .find(|p| p["id"] == id)
            .ok_or("PROFILE_DRIFT")?;
        for field in ["type", "remoteHost", "remotePort"] {
            if actual[field] != original[field] {
                return Err("PROFILE_DRIFT");
            }
        }
        let remote_profile = |profile: &Value| {
            profile
                .get("remoteProfileId")
                .cloned()
                .unwrap_or_else(|| Value::String("default".into()))
        };
        let actual_pin = inventory::pin(
            actual["remoteFingerprint"]
                .as_str()
                .ok_or("PROFILE_DRIFT")?,
        )
        .ok_or("PROFILE_DRIFT")?;
        let original_pin = inventory::pin(
            original["remoteFingerprint"]
                .as_str()
                .ok_or("PROFILE_DRIFT")?,
        )
        .ok_or("PROFILE_DRIFT")?;
        if remote_profile(actual) != remote_profile(original) || actual_pin != original_pin {
            return Err("PROFILE_DRIFT");
        }
        Ok(crate::digest(&bytes))
    }
    fn start(
        &self,
        configuration: &Configuration,
        name: &str,
        client_info: &Value,
        credential: ProbeCredential,
        generation: ProbeGeneration,
        now: u64,
    ) -> Result<ProbeFuture> {
        configuration.verify_current()?;
        if name == "connector" {
            let row = configuration.inventory.connector();
            let config = ConnectorProbeConfig {
                endpoint: endpoint(&row["local"])?,
                supported_api_versions: row["supported_api_versions"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .map(|v| v.as_u64().unwrap())
                    .collect(),
                minimum_contract_version: row["min_contract_version"].as_str().unwrap().into(),
                required_features: row["required_features"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .map(|v| v.as_str().unwrap().into())
                    .collect(),
            };
            Ok(Box::pin(async move {
                probe::connector_probe(&config, credential, generation, now, Duration::from_secs(2))
                    .await
            }))
        } else {
            let row = configuration
                .inventory
                .hosts()
                .iter()
                .find(|h| h["name"] == name)
                .ok_or("INVENTORY_INVALID")?;
            let profile = configuration
                .profile_index
                .profile(row["profile"].as_str().unwrap())
                .ok_or("PROFILE_DRIFT")?;
            let pin = inventory::pin(
                profile["remoteFingerprint"]
                    .as_str()
                    .ok_or("PROFILE_DRIFT")?,
            )
            .ok_or("PROFILE_DRIFT")?;
            let config = BatProbeConfig {
                endpoint: endpoint(&row["local"])?,
                certificate_pin: pin,
                remote_profile_id: row["bat"]["remote_profile_id"].as_str().unwrap().into(),
                required_workspace_ids: row["workspace_bindings"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .filter(|b| b["required"] == true)
                    .map(|b| b["workspace_id"].as_str().unwrap().into())
                    .collect(),
                minimum_version: row["bat"]["min_version"].as_str().unwrap().into(),
                client_info: client_info.clone(),
            };
            Ok(Box::pin(async move {
                probe::bat_probe(&config, credential, generation, now, Duration::from_secs(5)).await
            }))
        }
    }
}
