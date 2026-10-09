//! Native-only credentials. No secret type implements Debug or crosses IPC.
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use zeroize::Zeroizing;

pub const MAX_BLOB: usize = 2560;
pub const MAX_TOKEN: usize = 512;

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Identity {
    pub server_id: String,
    pub principal_id: String,
}
impl Identity {
    pub fn validate(&self) -> Result<(), String> {
        if self.server_id.is_empty()
            || self.server_id.len() > 128
            || self.principal_id.is_empty()
            || self.principal_id.len() > 128
            || !self
                .server_id
                .bytes()
                .chain(self.principal_id.bytes())
                .all(|b| b.is_ascii_alphanumeric() || b == b'-')
        {
            return Err("Invalid central bootstrap identity".into());
        }
        Ok(())
    }
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Record {
    pub version: u8,
    pub binding: String,
    pub identity: Identity,
    pub token: Zeroizing<String>,
}
impl Record {
    pub fn decode(bytes: &[u8], binding: &str) -> Result<Self, String> {
        if bytes.len() > MAX_BLOB {
            return Err("Protected credential exceeds its bound".into());
        }
        let record: Self = serde_json::from_slice(bytes)
            .map_err(|_| "Protected credential is unreadable; explicitly replace it")?;
        if record.version != 1 || record.binding != binding {
            return Err("Protected credential belongs to another configuration".into());
        }
        record.identity.validate()?;
        validate_token(&record.token)?;
        Ok(record)
    }
    pub fn encode(&self) -> Result<Zeroizing<Vec<u8>>, String> {
        self.identity.validate()?;
        validate_token(&self.token)?;
        let bytes = Zeroizing::new(
            serde_json::to_vec(self).map_err(|_| "Unable to encode protected credential")?,
        );
        if bytes.len() > MAX_BLOB {
            return Err("Protected credential exceeds its bound".into());
        }
        Ok(bytes)
    }
}

pub fn validate_token(token: &str) -> Result<(), String> {
    if token.is_empty()
        || token.len() > MAX_TOKEN
        || !token
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b"-._~+/=".contains(&b))
    {
        return Err("Enter a Connector API token, without spaces or a Bearer prefix".into());
    }
    Ok(())
}

// Fixed namespace, no raw account/endpoint/secret in the OS reference. Length framing prevents collisions.
pub fn binding(endpoint: &str, actor: &str, contract: &str) -> String {
    let mut digest = Sha256::new();
    for part in [endpoint, actor, contract] {
        digest.update((part.len() as u64).to_be_bytes());
        digest.update(part.as_bytes());
    }
    format!("{:x}", digest.finalize())
}

#[derive(Clone, Copy, Deserialize)]
pub enum Locale {
    #[serde(rename = "en-US")]
    English,
    #[serde(rename = "zh-TW")]
    TraditionalChinese,
}

pub trait Vault: Send + Sync {
    fn supported(&self) -> bool;
    fn read(&self, binding: &str) -> Result<Option<Zeroizing<Vec<u8>>>, String>;
    fn write(&self, binding: &str, bytes: &[u8]) -> Result<(), String>;
    fn remove(&self, binding: &str) -> Result<(), String>;
    fn prompt(
        &self,
        actor: &str,
        endpoint: &str,
        locale: Locale,
        parent: isize,
    ) -> Result<Option<Zeroizing<String>>, String>;
}
pub struct OsVault;

#[cfg(not(windows))]
impl Vault for OsVault {
    fn supported(&self) -> bool {
        false
    }
    fn read(&self, _: &str) -> Result<Option<Zeroizing<Vec<u8>>>, String> {
        Ok(None)
    }
    fn write(&self, _: &str, _: &[u8]) -> Result<(), String> {
        Err("Protected enrollment requires Windows".into())
    }
    fn remove(&self, _: &str) -> Result<(), String> {
        Err("Protected enrollment requires Windows".into())
    }
    fn prompt(
        &self,
        _: &str,
        _: &str,
        _: Locale,
        _: isize,
    ) -> Result<Option<Zeroizing<String>>, String> {
        Err("Protected enrollment requires Windows".into())
    }
}

#[cfg(windows)]
mod windows {
    use super::*;
    use std::{
        mem::size_of,
        ptr::{null, null_mut},
    };
    use windows_sys::Win32::{
        Foundation::{GetLastError, ERROR_CANCELLED, ERROR_NOT_FOUND},
        Security::Credentials::*,
    };
    use zeroize::Zeroize;
    fn wide(s: &str) -> Vec<u16> {
        s.encode_utf16().chain(Some(0)).collect()
    }
    fn target(binding: &str) -> Result<Vec<u16>, String> {
        if binding.len() != 64 || !binding.bytes().all(|b| b.is_ascii_hexdigit()) {
            return Err("Invalid native credential reference".into());
        }
        Ok(wide(&format!("BetterAgentDashboard/central/v1/{binding}")))
    }
    // CredRead's allocation can contain the secret even if decoding subsequently fails.
    struct ReadBuffer(*mut CREDENTIALW);
    impl Drop for ReadBuffer {
        fn drop(&mut self) {
            unsafe {
                let record = &mut *self.0;
                if !record.CredentialBlob.is_null()
                    && record.CredentialBlobSize <= CRED_MAX_CREDENTIAL_BLOB_SIZE
                {
                    std::slice::from_raw_parts_mut(
                        record.CredentialBlob,
                        record.CredentialBlobSize as usize,
                    )
                    .zeroize();
                }
                CredFree(self.0.cast());
            }
        }
    }
    impl Vault for OsVault {
        fn supported(&self) -> bool {
            true
        }
        fn read(&self, binding: &str) -> Result<Option<Zeroizing<Vec<u8>>>, String> {
            let name = target(binding)?;
            let mut raw = null_mut();
            // Generic credentials are private to this Windows user; no domain/network login occurs.
            if unsafe { CredReadW(name.as_ptr(), CRED_TYPE_GENERIC, 0, &mut raw) } == 0 {
                if unsafe { GetLastError() } == ERROR_NOT_FOUND {
                    return Ok(None);
                }
                return Err("Windows Credential Manager is unavailable".into());
            }
            if raw.is_null() {
                return Err("Windows returned no credential".into());
            }
            let buffer = ReadBuffer(raw);
            let record = unsafe { &*buffer.0 };
            if record.Type != CRED_TYPE_GENERIC
                || record.CredentialBlobSize as usize > MAX_BLOB
                || record.CredentialBlob.is_null()
                || record.CredentialBlobSize == 0
            {
                return Err("Invalid protected credential record".into());
            }
            Ok(Some(Zeroizing::new(unsafe {
                std::slice::from_raw_parts(
                    record.CredentialBlob,
                    record.CredentialBlobSize as usize,
                )
                .to_vec()
            })))
        }
        fn write(&self, binding: &str, bytes: &[u8]) -> Result<(), String> {
            let mut name = target(binding)?;
            if bytes.is_empty() || bytes.len() > MAX_BLOB {
                return Err("Invalid credential size".into());
            }
            let record = CREDENTIALW {
                Type: CRED_TYPE_GENERIC,
                TargetName: name.as_mut_ptr(),
                CredentialBlobSize: bytes.len() as u32,
                CredentialBlob: bytes.as_ptr().cast_mut(),
                Persist: CRED_PERSIST_LOCAL_MACHINE,
                ..Default::default()
            };
            if unsafe { CredWriteW(&record, 0) } == 0 {
                return Err(
                    "Unable to save in Windows Credential Manager; previous credential retained"
                        .into(),
                );
            }
            Ok(())
        }
        fn remove(&self, binding: &str) -> Result<(), String> {
            let name = target(binding)?;
            if unsafe { CredDeleteW(name.as_ptr(), CRED_TYPE_GENERIC, 0) } == 0
                && unsafe { GetLastError() } != ERROR_NOT_FOUND
            {
                return Err("Unable to remove the Windows credential".into());
            }
            Ok(())
        }
        fn prompt(
            &self,
            actor: &str,
            endpoint: &str,
            locale: Locale,
            parent: isize,
        ) -> Result<Option<Zeroizing<String>>, String> {
            prompt_with(
                actor,
                endpoint,
                locale,
                parent,
                |info, target, username, password| {
                    let mut save = 0;
                    // Generic bearer token, fixed username, no automatic persistence before verification.
                    unsafe {
                        CredUIPromptForCredentialsW(
                            info,
                            target.as_ptr(),
                            null(),
                            0,
                            username.as_mut_ptr(),
                            username.len() as u32,
                            password.as_mut_ptr(),
                            password.len() as u32,
                            &mut save,
                            PROMPT_FLAGS,
                        )
                    }
                },
            )
        }
    }
    const PROMPT_FLAGS: CREDUI_FLAGS = CREDUI_FLAGS_GENERIC_CREDENTIALS
        | CREDUI_FLAGS_ALWAYS_SHOW_UI
        | CREDUI_FLAGS_DO_NOT_PERSIST
        | CREDUI_FLAGS_KEEP_USERNAME;
    fn prompt_with(
        actor: &str,
        endpoint: &str,
        locale: Locale,
        parent: isize,
        call: impl FnOnce(&CREDUI_INFOW, &[u16], &mut [u16], &mut [u16]) -> u32,
    ) -> Result<Option<Zeroizing<String>>, String> {
        let caption = wide("Better Agent Dashboard");
        let message = wide(&match locale {
                Locale::English => format!("Connector: {endpoint}\nPaste the Connector API token in Password. It will be verified before saving for this Windows account."),
                Locale::TraditionalChinese => format!("Connector：{endpoint}\n請在密碼欄貼上 Connector API token。驗證成功後才會儲存至此 Windows 帳戶。"),
            });
        let info = CREDUI_INFOW {
            cbSize: size_of::<CREDUI_INFOW>() as u32,
            hwndParent: parent as _,
            pszMessageText: message.as_ptr(),
            pszCaptionText: caption.as_ptr(),
            hbmBanner: null_mut(),
        };
        let target = wide("BetterAgentDashboard/central/enrollment");
        let mut username = Zeroizing::new(vec![0u16; CREDUI_MAX_USERNAME_LENGTH as usize + 1]);
        let actor: Vec<u16> = actor.encode_utf16().collect();
        if actor.len() >= username.len() {
            return Err("Configured actor is too long".into());
        }
        username[..actor.len()].copy_from_slice(&actor);
        let mut password = Zeroizing::new(vec![0u16; MAX_TOKEN + 1]);
        let result = call(&info, &target, &mut username, &mut password);
        if result == ERROR_CANCELLED {
            return Ok(None);
        }
        if result != 0 {
            return Err("Unable to open the Windows credential dialog".into());
        }
        let length = password
            .iter()
            .position(|c| *c == 0)
            .ok_or("Credential exceeds its bound")?;
        // Only the ASCII bearer alphabet is accepted; no fallible UTF-16 conversion leaves a partial secret.
        let mut token = Zeroizing::new(String::with_capacity(length));
        for c in &password[..length] {
            if *c > 127 {
                return Err("Connector API tokens must use ASCII characters".into());
            }
            token.push(*c as u8 as char);
        }
        validate_token(&token)?;
        Ok(Some(token))
    }
    #[cfg(test)]
    mod tests {
        use super::*;
        #[test]
        fn native_dialog_has_fixed_actor_bounded_secret_and_no_automatic_persistence() {
            assert_ne!(PROMPT_FLAGS & CREDUI_FLAGS_GENERIC_CREDENTIALS, 0);
            assert_ne!(PROMPT_FLAGS & CREDUI_FLAGS_KEEP_USERNAME, 0);
            assert_ne!(PROMPT_FLAGS & CREDUI_FLAGS_DO_NOT_PERSIST, 0);
            assert_eq!(PROMPT_FLAGS & CREDUI_FLAGS_PERSIST, 0);
            let token = prompt_with(
                "fixture-actor",
                "https://central.example/",
                Locale::TraditionalChinese,
                0,
                |info, target, username, password| {
                    assert_eq!(info.cbSize as usize, size_of::<CREDUI_INFOW>());
                    assert_eq!(target, wide("BetterAgentDashboard/central/enrollment"));
                    assert_eq!(&username[..14], wide("fixture-actor").as_slice());
                    assert_eq!(password.len(), MAX_TOKEN + 1);
                    assert!(password.iter().all(|n| *n == 0));
                    for (out, input) in password.iter_mut().zip("synthetic-token".encode_utf16()) {
                        *out = input;
                    }
                    0
                },
            )
            .unwrap()
            .unwrap();
            assert_eq!(token.as_str(), "synthetic-token");
        }
        #[test]
        fn native_dialog_cancel_failure_and_malformed_secret_do_not_produce_a_token() {
            for result in [ERROR_CANCELLED, 87] {
                let output = prompt_with(
                    "fixture",
                    "https://central.example/",
                    Locale::English,
                    0,
                    |_, _, _, password| {
                        password[0] = b'x' as u16;
                        result
                    },
                );
                if result == ERROR_CANCELLED {
                    assert!(output.unwrap().is_none());
                } else {
                    assert!(output.is_err());
                }
            }
            assert!(prompt_with(
                "fixture",
                "https://central.example/",
                Locale::English,
                0,
                |_, _, _, password| {
                    password.fill(b'x' as u16);
                    0
                }
            )
            .is_err());
            assert!(prompt_with(
                "fixture",
                "https://central.example/",
                Locale::English,
                0,
                |_, _, _, password| {
                    password[0] = 0xD800;
                    0
                }
            )
            .is_err());
            assert!(target("../other-credential").is_err());
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn record_is_bound_bounded_and_never_accepts_headers() {
        let key = binding("https://central.example/", "operator", "2026-10-08");
        assert_ne!(
            key,
            binding("https://other.example/", "operator", "2026-10-08")
        );
        assert_ne!(
            key,
            binding("https://central.example/", "other", "2026-10-08")
        );
        let record = Record {
            version: 1,
            binding: key.clone(),
            identity: Identity {
                server_id: "fixture".into(),
                principal_id: "principal".into(),
            },
            token: Zeroizing::new("synthetic-fixture-token".into()),
        };
        let encoded = record.encode().unwrap();
        assert!(Record::decode(&encoded, &key).is_ok());
        assert!(Record::decode(&encoded, &"f".repeat(64)).is_err());
        assert!(Record::decode(&vec![b'a'; MAX_BLOB + 1], &key).is_err());
        for token in [
            "",
            "Bearer value",
            "a\r\nX-Test: secret",
            "nonasciié",
            &"x".repeat(MAX_TOKEN + 1),
        ] {
            assert!(validate_token(token).is_err());
        }
    }
}
