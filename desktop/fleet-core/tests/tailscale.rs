use bat_fleet_core::tailscale::{login_state, LoginState, Phase, Spawn, Store, STATUS_LIMIT};
use std::cell::Cell;
#[allow(dead_code)]
mod support;
use support::Fixture;
fn store(root: &Fixture) -> Store {
    Store::new(&root.0, &"a".repeat(64)).unwrap()
}
#[test]
fn status_projects_only_exact_known_states() {
    for (state, expected) in [
        ("NeedsLogin", LoginState::NeedsLogin),
        ("NeedsMachineAuth", LoginState::NeedsApproval),
        ("Stopped", LoginState::Stopped),
        ("Starting", LoginState::Starting),
        ("Running", LoginState::Running),
        ("NoState", LoginState::Unknown),
        ("FutureState", LoginState::Unknown),
    ] {
        let bytes=serde_json::to_vec(&serde_json::json!({"BackendState":state,"AuthURL":"https://private.invalid/secret","User":{"private":"account"},"Peer":{}})).unwrap();
        assert_eq!(login_state(&bytes, true), expected);
        assert_eq!(login_state(&bytes, false), LoginState::Unknown);
        assert!(!serde_json::to_string(&login_state(&bytes, true))
            .unwrap()
            .contains("private"));
    }
    for bytes in [
        br#"{"BackendState":"Running","backendstate":"NeedsLogin"}"#.as_slice(),
        b"not-json",
        b"{}",
        br#"{"BackendState":true}"#,
        br#"{"BackendState":"Running"} trailing"#,
    ] {
        assert_eq!(login_state(bytes, true), LoginState::Unknown);
    }
    assert_eq!(
        login_state(&vec![b' '; STATUS_LIMIT + 1], true),
        LoginState::Unknown
    );
}
#[test]
fn original_receipt_survives_restart_policy_change_and_no_resend() {
    let f = Fixture::new();
    let id = "b".repeat(32);
    let calls = Cell::new(0);
    let receipt = store(&f)
        .open(
            &id,
            || Ok(()),
            || {
                calls.set(calls.get() + 1);
                Spawn::Started
            },
        )
        .unwrap();
    assert_eq!(receipt.phase, Phase::Started);
    assert_eq!(
        store(&f)
            .open(&id, || Err("policy changed"), || panic!("must not spawn"))
            .unwrap(),
        receipt
    );
    assert_eq!(calls.get(), 1);
    assert_eq!(store(&f).receipt(&id).unwrap(), Some(receipt));
}
#[test]
fn ambiguous_launch_blocks_original_resend_and_replacement() {
    let f = Fixture::new();
    let id = "b".repeat(32);
    let receipt = store(&f).open(&id, || Ok(()), || Spawn::Uncertain).unwrap();
    assert_eq!(receipt.phase, Phase::Uncertain);
    assert_eq!(
        store(&f).open(&id, || Ok(()), || panic!("resend")).unwrap(),
        receipt
    );
    assert_eq!(
        store(&f)
            .open(&"c".repeat(32), || Ok(()), || panic!("replacement"))
            .unwrap_err(),
        "TAILSCALE_OPEN_UNCERTAIN"
    );
}
#[test]
fn launch_intent_is_durable_before_effect_and_crash_retains_it() {
    let f = Fixture::new();
    let id = "b".repeat(32);
    let result = std::panic::catch_unwind(|| {
        store(&f).open(
            &id,
            || Ok(()),
            || {
                assert_eq!(
                    store(&f).receipt(&id).unwrap().unwrap().phase,
                    Phase::Uncertain
                );
                panic!("simulated crash");
            },
        )
    });
    assert!(result.is_err());
    assert_eq!(store(&f).latest().unwrap().unwrap().phase, Phase::Uncertain);
}
#[test]
fn final_ticket_or_configuration_change_prevents_spawn() {
    let f = Fixture::new();
    let checks = Cell::new(0);
    let value = store(&f)
        .open(
            &"b".repeat(32),
            || {
                checks.set(checks.get() + 1);
                if checks.get() == 1 {
                    Ok(())
                } else {
                    Err("FLEET_STOP_REQUESTED")
                }
            },
            || panic!("stopped effect"),
        )
        .unwrap();
    assert_eq!(value.phase, Phase::NotStarted);
    assert_eq!(
        store(&f)
            .open(&"c".repeat(32), || Ok(()), || Spawn::Started)
            .unwrap()
            .phase,
        Phase::Started
    );
}
#[test]
fn admission_refusal_keeps_storage_unchanged() {
    let f = Fixture::new();
    assert_eq!(
        store(&f)
            .open(
                &"b".repeat(32),
                || Err("FLEET_STOP_REQUESTED"),
                || panic!("stopped")
            )
            .unwrap_err(),
        "FLEET_STOP_REQUESTED"
    );
    assert!(store(&f).latest().unwrap().is_none());
}
#[test]
fn changed_journal_after_spawn_is_not_overwritten_or_replayed() {
    let f = Fixture::new();
    let path =
        f.0.join(format!("bat-tailscale-open-{}.json", "a".repeat(64)));
    assert!(store(&f)
        .open(
            &"b".repeat(32),
            || Ok(()),
            || {
                std::fs::write(&path, b"edited").unwrap();
                Spawn::Started
            }
        )
        .is_err());
    assert_eq!(std::fs::read(&path).unwrap(), b"edited");
    assert!(store(&f).latest().is_err());
    assert!(store(&f)
        .open(&"b".repeat(32), || Ok(()), || panic!("resend"))
        .is_err());
}
#[test]
fn account_login_scopes_and_malformed_ids_are_isolated() {
    let f = Fixture::new();
    let id = "b".repeat(32);
    store(&f).open(&id, || Ok(()), || Spawn::Started).unwrap();
    assert!(Store::new(&f.0, &"c".repeat(64))
        .unwrap()
        .receipt(&id)
        .unwrap()
        .is_none());
    for id in ["../escape", "ABC", "", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaA"] {
        assert!(store(&f).open(id, || Ok(()), || panic!("bad id")).is_err());
    }
}
#[test]
fn proven_spawn_refusal_does_not_turn_into_an_automatic_retry() {
    let f = Fixture::new();
    let id = "b".repeat(32);
    assert_eq!(
        store(&f)
            .open(&id, || Ok(()), || Spawn::NotStarted)
            .unwrap()
            .phase,
        Phase::NotStarted
    );
    assert_eq!(
        store(&f)
            .open(&id, || Ok(()), || panic!("retry"))
            .unwrap()
            .phase,
        Phase::NotStarted
    );
}
