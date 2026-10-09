//! Byte fixtures independent of the production frame encoder.
use super::*;
use tokio::io::{duplex, AsyncReadExt, AsyncWriteExt};

#[tokio::test]
async fn malformed_frames_are_bounded_before_payload_and_use_fixed_reasons() {
    let cases: &[(&[u8], &str)] = &[
        (&[0x81], "truncated_header"),
        (&[0x81, 126, 0], "truncated_length"),
        (&[0x81, 2, b'a'], "truncated_payload"),
        (&[0xc1, 0], "frame_flags"),
        (&[0x81, 128], "frame_flags"),
        (&[0x81, 126, 0, 125], "frame_length"),
        (&[0x81, 127, 0, 0, 0, 0, 0, 0, 255, 255], "frame_length"),
        (&[0x81, 127, 128, 0, 0, 0, 0, 1, 0, 0], "frame_length"),
        (&[9, 0], "control_fragmented"),
        (&[0x89, 126, 0, 126], "control_frame_too_long"),
        (&[0x82, 0], "frame_opcode"),
        (&[0x80, 0], "fragment_sequence"),
        (&[1, 1, b'x', 0x81, 0], "fragment_sequence"),
        (&[0x81, 1, 255], "text_encoding"),
        (&[0x88, 0], "peer_closed"),
        (&[0x81, 127, 0, 0, 0, 0, 1, 0, 0, 1], "message_too_large"),
    ];
    for (bytes, reason) in cases {
        let (a, mut b) = duplex(64);
        b.write_all(bytes).await.unwrap();
        b.shutdown().await.unwrap();
        let result = Wire(a).read_text().await;
        assert_eq!(result.unwrap_err(), *reason, "{bytes:?}");
    }
}
#[tokio::test]
async fn fragmented_message_budget_excludes_ping_and_accepts_exact_limit() {
    let (a, mut b) = duplex(65536);
    let peer = tokio::spawn(async move {
        b.write_all(&[1, 127, 0, 0, 0, 0, 0, 255, 255, 255])
            .await
            .unwrap(); // 16MiB - 1
        b.write_all(&vec![b'a'; MESSAGE_LIMIT - 1]).await.unwrap();
        b.write_all(&[0x89, 125]).await.unwrap();
        b.write_all(&[b'p'; 125]).await.unwrap();
        let mut response = [0; 131];
        b.read_exact(&mut response).await.unwrap();
        assert_eq!(&response[..2], &[0x8a, 0xfd]);
        for i in 0..125 {
            assert_eq!(response[6 + i] ^ response[2 + i % 4], b'p');
        }
        b.write_all(&[0x80, 1, b'z']).await.unwrap();
    });
    let result = Wire(a).read_text().await.unwrap();
    assert_eq!(result.len(), MESSAGE_LIMIT);
    assert_eq!(result[MESSAGE_LIMIT - 1], b'z');
    peer.await.unwrap();
}
#[tokio::test]
async fn cumulative_limit_rejects_before_reading_missing_second_payload() {
    let (a, mut b) = duplex(65536);
    let peer = tokio::spawn(async move {
        b.write_all(&[1, 127, 0, 0, 0, 0, 1, 0, 0, 0])
            .await
            .unwrap();
        b.write_all(&vec![b'a'; MESSAGE_LIMIT]).await.unwrap();
        b.write_all(&[0x80, 1]).await.unwrap();
        // If the reader tries to consume the payload, it gets truncated_payload.
        b.shutdown().await.unwrap();
    });
    assert_eq!(Wire(a).read_text().await.unwrap_err(), "message_too_large");
    peer.await.unwrap();
}
#[tokio::test]
async fn ping_write_failure_and_partial_unicode_do_not_yield_a_message() {
    let (a, mut b) = duplex(64);
    b.write_all(&[0x89, 1, b'p']).await.unwrap();
    drop(b);
    assert_eq!(Wire(a).read_text().await.unwrap_err(), "pong_write_failed");
    let (a, mut b) = duplex(64);
    b.write_all(&[1, 1, 0xe5, 0x80, 1, 0xb7]).await.unwrap();
    assert_eq!(Wire(a).read_text().await.unwrap_err(), "text_encoding");
}
#[tokio::test]
async fn invalid_upgrade_headers_never_authenticate() {
    for response in [
        "HTTP/1.1 200 OK\r\n\r\n",
        "HTTP/1.1 101 OK\r\ninvalid\r\n\r\n",
        "HTTP/1.1 101 OK\r\nUpgrade: websocket\r\nupgrade: websocket\r\n\r\n",
        "HTTP/1.1 101 OK\r\nConnection: Upgrade\r\n\r\n",
    ] {
        let (a, mut b) = duplex(1024);
        let peer = tokio::spawn(async move {
            let mut request = Vec::new();
            while !request.ends_with(b"\r\n\r\n") {
                request.push(b.read_u8().await.unwrap());
            }
            b.write_all(response.as_bytes()).await.unwrap();
        });
        let reason = Wire(a).upgrade("127.0.0.1:1234").await.unwrap_err();
        assert!(["upgrade_status", "upgrade_header", "upgrade_accept"].contains(&reason));
        peer.await.unwrap();
    }
}
