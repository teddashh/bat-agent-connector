//! Bounded BAT v2 transport port of Fleet Kit fleet-transport.cs.
//! Only auth and readonly workspace load are exposed by the public probe module.
use base64::{engine::general_purpose::STANDARD, Engine};
use rustls::{
    client::danger::{HandshakeSignatureValid, ServerCertVerified, ServerCertVerifier},
    crypto::{verify_tls12_signature, verify_tls13_signature, CryptoProvider},
    pki_types::{CertificateDer, ServerName, UnixTime},
    DigitallySignedStruct, Error, SignatureScheme,
};
use sha1::{Digest, Sha1};
use std::{
    collections::HashMap,
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
};
use tokio::io::{AsyncRead, AsyncReadExt, AsyncWrite, AsyncWriteExt};
use zeroize::Zeroizing;

pub(crate) const MESSAGE_LIMIT: usize = 16 * 1024 * 1024;
pub(crate) type WireResult<T> = Result<T, &'static str>;

pub(crate) struct PinnedCertificate {
    pub pin: String,
    pub mismatch: Arc<AtomicBool>,
    pub provider: Arc<CryptoProvider>,
}
impl std::fmt::Debug for PinnedCertificate {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("PinnedCertificate")
    }
}
impl ServerCertVerifier for PinnedCertificate {
    fn verify_server_cert(
        &self,
        end: &CertificateDer<'_>,
        _: &[CertificateDer<'_>],
        _: &ServerName<'_>,
        _: &[u8],
        _: UnixTime,
    ) -> Result<ServerCertVerified, Error> {
        if !crate::digest(end.as_ref()).eq_ignore_ascii_case(&self.pin) {
            self.mismatch.store(true, Ordering::Relaxed);
            return Err(Error::General("TLS_IDENTITY_MISMATCH".into()));
        }
        // The configured full-certificate pin replaces PKI name/chain trust, as in
        // Kit. It does NOT replace proof that the peer holds the certificate key.
        Ok(ServerCertVerified::assertion())
    }
    fn verify_tls12_signature(
        &self,
        message: &[u8],
        cert: &CertificateDer<'_>,
        dss: &DigitallySignedStruct,
    ) -> Result<HandshakeSignatureValid, Error> {
        verify_tls12_signature(
            message,
            cert,
            dss,
            &self.provider.signature_verification_algorithms,
        )
    }
    fn verify_tls13_signature(
        &self,
        message: &[u8],
        cert: &CertificateDer<'_>,
        dss: &DigitallySignedStruct,
    ) -> Result<HandshakeSignatureValid, Error> {
        verify_tls13_signature(
            message,
            cert,
            dss,
            &self.provider.signature_verification_algorithms,
        )
    }
    fn supported_verify_schemes(&self) -> Vec<SignatureScheme> {
        self.provider
            .signature_verification_algorithms
            .supported_schemes()
    }
}

pub(crate) struct Wire<S>(pub S);
impl<S: AsyncRead + AsyncWrite + Unpin> Wire<S> {
    async fn read(&mut self, count: usize, reason: &'static str) -> WireResult<Vec<u8>> {
        let mut bytes = vec![0; count];
        self.0.read_exact(&mut bytes).await.map_err(|_| reason)?;
        Ok(bytes)
    }
    async fn write(&mut self, bytes: &[u8]) -> WireResult<()> {
        self.0.write_all(bytes).await.map_err(|_| "write_failed")?;
        self.0.flush().await.map_err(|_| "write_failed")
    }
    pub async fn upgrade(&mut self, authority: &str) -> WireResult<()> {
        let key = STANDARD.encode(rand::random::<[u8; 16]>());
        self.write(format!("GET / HTTP/1.1\r\nHost: {authority}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").as_bytes()).await?;
        let mut bytes = Vec::new();
        while bytes.len() < 16384 {
            bytes.extend(self.read(1, "truncated_upgrade").await?);
            if !bytes.ends_with(b"\r\n\r\n") {
                continue;
            }
            let text = std::str::from_utf8(&bytes).map_err(|_| "upgrade_header")?;
            let mut lines = text.split("\r\n");
            if !lines
                .next()
                .unwrap_or_default()
                .starts_with("HTTP/1.1 101 ")
            {
                return Err("upgrade_status");
            }
            let mut headers = HashMap::new();
            for line in lines.filter(|line| !line.is_empty()) {
                let (name, value) = line.split_once(':').ok_or("upgrade_header")?;
                if name.trim().is_empty()
                    || headers
                        .insert(name.trim().to_ascii_lowercase(), value.trim())
                        .is_some()
                {
                    return Err("upgrade_header");
                }
            }
            let expected = STANDARD.encode(Sha1::digest(
                format!("{key}258EAFA5-E914-47DA-95CA-C5AB0DC85B11").as_bytes(),
            ));
            if !headers
                .get("upgrade")
                .is_some_and(|v| v.eq_ignore_ascii_case("websocket"))
                || !headers.get("connection").is_some_and(|v| {
                    v.split(',')
                        .any(|x| x.trim().eq_ignore_ascii_case("upgrade"))
                })
                || headers.get("sec-websocket-accept") != Some(&expected.as_str())
            {
                return Err("upgrade_accept");
            }
            return Ok(());
        }
        Err("upgrade_too_large")
    }
    async fn send(&mut self, opcode: u8, payload: &[u8]) -> WireResult<()> {
        if payload.len() > MESSAGE_LIMIT {
            return Err("message_too_large");
        }
        // Zero the owned encoded auth frame as well as the caller's plaintext buffer.
        let mut frame = Zeroizing::new(Vec::with_capacity(payload.len() + 14));
        frame.push(0x80 | opcode);
        match payload.len() {
            0..=125 => frame.push(0x80 | payload.len() as u8),
            126..=65535 => {
                frame.push(0xfe);
                frame.extend((payload.len() as u16).to_be_bytes());
            }
            _ => {
                frame.push(0xff);
                frame.extend((payload.len() as u64).to_be_bytes());
            }
        }
        let mask = rand::random::<[u8; 4]>();
        frame.extend(mask);
        frame.extend(payload.iter().enumerate().map(|(i, b)| b ^ mask[i % 4]));
        self.write(&frame).await
    }
    pub async fn send_text(&mut self, payload: &[u8]) -> WireResult<()> {
        self.send(1, payload).await
    }
    pub async fn read_text(&mut self) -> WireResult<Zeroizing<Vec<u8>>> {
        let mut message = Zeroizing::new(Vec::new());
        let mut fragmented = false;
        loop {
            let header = self.read(2, "truncated_header").await?;
            let fin = header[0] & 0x80 != 0;
            let op = header[0] & 15;
            if header[0] & 0x70 != 0 || header[1] & 0x80 != 0 {
                return Err("frame_flags");
            }
            let length = match header[1] & 127 {
                126 => {
                    let bytes = self.read(2, "truncated_length").await?;
                    let n = u16::from_be_bytes(bytes.try_into().unwrap()) as u64;
                    if n < 126 {
                        return Err("frame_length");
                    }
                    n
                }
                127 => {
                    let bytes = self.read(8, "truncated_length").await?;
                    let n = u64::from_be_bytes(bytes.try_into().unwrap());
                    if n <= 65535 || n >> 63 != 0 {
                        return Err("frame_length");
                    }
                    n
                }
                n => n as u64,
            };
            let control = op >= 8;
            if control && !fin {
                return Err("control_fragmented");
            }
            if control && length > 125 {
                return Err("control_frame_too_long");
            }
            if ![0, 1, 8, 9, 10].contains(&op) {
                return Err("frame_opcode");
            }
            if !control {
                if (op == 1 && fragmented) || (op == 0 && !fragmented) {
                    return Err("fragment_sequence");
                }
                // Reject before allocating/reading advertised payload; control bytes do not count.
                if length > MESSAGE_LIMIT as u64
                    || length + message.len() as u64 > MESSAGE_LIMIT as u64
                {
                    return Err("message_too_large");
                }
            }
            let payload = Zeroizing::new(self.read(length as usize, "truncated_payload").await?);
            match op {
                8 => return Err("peer_closed"),
                9 => {
                    self.send(10, &payload)
                        .await
                        .map_err(|_| "pong_write_failed")?;
                    continue;
                }
                10 => continue,
                _ => message.extend_from_slice(&payload),
            }
            if fin {
                std::str::from_utf8(&message).map_err(|_| "text_encoding")?;
                return Ok(message);
            }
            fragmented = true;
        }
    }
}

#[cfg(test)]
#[path = "probe_wire_tests.rs"]
mod tests;
