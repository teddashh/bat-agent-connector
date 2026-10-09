//! The Kit's independent connection/window/dashboard choices; persistence locks belong to the OS adapter.
use crate::{inventory::Inventory, strict_json, Result};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashSet;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Preferences {
    pub version: u32,
    pub connections: Vec<String>,
    pub profiles: Vec<String>,
    pub dashboard: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub known: Option<Vec<String>>,
}
/// IPC may carry these logical choices; private snapshots and native paths never do.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Choices {
    pub connections: Vec<String>,
    pub profiles: Vec<String>,
    pub dashboard: bool,
}
fn names(inv: &Inventory, field: &str) -> Vec<String> {
    inv.hosts()
        .iter()
        .map(|h| h[field].as_str().unwrap().to_owned())
        .collect()
}
fn canonical(values: &[String], allowed: &[String]) -> Vec<String> {
    let mut seen = HashSet::new();
    values
        .iter()
        .filter_map(|s| allowed.iter().find(|v| v.eq_ignore_ascii_case(s)))
        .filter(|s| seen.insert((*s).clone()))
        .cloned()
        .collect()
}
impl Preferences {
    /// An explicit complete picker choice. Prerequisites are returned by launch_plan,
    /// not silently written into the independent saved connection selection.
    pub fn choose(inv: &Inventory, chosen: &Choices) -> Result<Self> {
        let mut allowed_connections = names(inv, "name");
        allowed_connections.push("connector".into());
        let mut allowed_profiles = names(inv, "profile");
        allowed_profiles.push("default".into());
        let connections = canonical(&chosen.connections, &allowed_connections);
        let profiles = canonical(&chosen.profiles, &allowed_profiles);
        if connections.len() != chosen.connections.len()
            || profiles.len() != chosen.profiles.len()
            || (chosen.dashboard || connections.iter().any(|n| n == "connector"))
                && !inv.connector()["ssh_alias"].is_string()
        {
            return Err("SELECTION_INVALID");
        }
        Ok(Self {
            version: 1,
            connections,
            profiles,
            dashboard: chosen.dashboard,
            known: Some(names(inv, "name")),
        })
    }
    pub fn defaults(inv: &Inventory) -> Self {
        Self {
            version: 1,
            connections: names(inv, "name"),
            profiles: names(inv, "profile"),
            dashboard: false,
            known: None,
        }
    }
    pub fn load(inv: &Inventory, bytes: Option<&[u8]>, legacy: Option<&[u8]>) -> Result<Self> {
        let mut out = Self::defaults(inv);
        let mut allowed_connections = names(inv, "name");
        allowed_connections.push("connector".into());
        let mut allowed_profiles = names(inv, "profile");
        allowed_profiles.push("default".into());
        if let Some(bytes) = bytes {
            let raw: Self = serde_json::from_value(strict_json::parse(bytes, 262144)?)
                .map_err(|_| "SELECTION_INVALID")?;
            if raw.version != 1
                || raw.connections.len() > 1000
                || raw.profiles.len() > 1000
                || raw.known.as_ref().is_some_and(|v| v.len() > 1000)
            {
                return Err("SELECTION_INVALID");
            }
            out.connections = canonical(&raw.connections, &allowed_connections);
            out.profiles = canonical(&raw.profiles, &allowed_profiles);
            out.dashboard = raw.dashboard;
            if let Some(known) = &raw.known {
                for host in inv.hosts() {
                    let name = host["name"].as_str().unwrap();
                    if !known.iter().any(|v| v.eq_ignore_ascii_case(name)) {
                        if !out.connections.iter().any(|v| v == name) {
                            out.connections.push(name.into());
                        }
                        let profile = host["profile"].as_str().unwrap();
                        if !out.profiles.iter().any(|v| v == profile) {
                            out.profiles.push(profile.into());
                        }
                    }
                }
            }
            out.known = raw.known;
        } else if let Some(legacy) = legacy {
            let doc = strict_json::parse(legacy, 262144)?;
            let map = doc.as_object().ok_or("SELECTION_INVALID")?;
            if map.values().any(|v| !v.is_boolean()) {
                return Err("SELECTION_INVALID");
            }
            out.profiles = canonical(
                &map.iter()
                    .filter(|(_, v)| **v == Value::Bool(true))
                    .map(|(k, _)| k.clone())
                    .collect::<Vec<_>>(),
                &allowed_profiles,
            );
        }
        Ok(out)
    }
    /// Caller must CAS preference bytes + configuration + owner epoch under the shared file lock.
    pub fn set_connections(&self, inv: &Inventory, chosen: &[String]) -> Result<Self> {
        let mut allowed = names(inv, "name");
        allowed.push("connector".into());
        let connections = canonical(chosen, &allowed);
        if chosen.len() != connections.len() {
            return Err("SELECTION_INVALID");
        }
        let mut out = self.clone();
        out.connections = connections;
        out.profiles.retain(|profile| {
            profile == "default"
                || inv.hosts().iter().any(|host| {
                    host["profile"] == *profile
                        && out.connections.iter().any(|c| host["name"] == *c)
                })
        });
        if !out.connections.iter().any(|c| c == "connector") {
            out.dashboard = false;
        }
        out.known = Some(names(inv, "name"));
        Ok(out)
    }
    pub fn persisted(&self, inv: &Inventory) -> Result<Vec<u8>> {
        let mut out = self.clone();
        out.known = Some(names(inv, "name"));
        serde_json::to_vec_pretty(&out).map_err(|_| "SELECTION_INVALID")
    }
}

#[derive(Debug, PartialEq, Eq)]
pub struct LaunchPlan {
    pub connect: Vec<String>,
    pub added: Vec<String>,
    pub open: Vec<String>,
    pub dashboard: bool,
    pub connector: bool,
    pub dashboard_only: bool,
}
pub fn launch_plan(inv: &Inventory, prefs: &Preferences) -> LaunchPlan {
    let mut connect = prefs.connections.clone();
    let mut added = Vec::new();
    let mut open = Vec::new();
    for profile in &prefs.profiles {
        if profile == "default" {
            open.push(profile.clone());
            continue;
        }
        if let Some(host) = inv.hosts().iter().find(|h| h["profile"] == *profile) {
            open.push(profile.clone());
            let name = host["name"].as_str().unwrap();
            if !connect.iter().any(|n| n == name) {
                connect.push(name.into());
                added.push(name.into());
            }
        }
    }
    let configured = inv.connector()["ssh_alias"].is_string();
    let dashboard = prefs.dashboard && configured;
    let connector = configured && (dashboard || connect.iter().any(|c| c == "connector"));
    if connector && !connect.iter().any(|c| c == "connector") {
        connect.push("connector".into());
    }
    if !connector {
        connect.retain(|c| c != "connector");
    }
    LaunchPlan {
        dashboard_only: open.is_empty() && dashboard,
        connect,
        added,
        open,
        dashboard,
        connector,
    }
}
