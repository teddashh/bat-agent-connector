//! Exercise every affected entry point using the GLib selected by the app lockfile.
//! CI also runs this target with --release: optimization exposed the original UB.
#![cfg(target_os = "linux")]

use glib::prelude::*;

#[test]
fn string_iterator_reads_all_affected_entry_points() {
    let strings = ["first", "", "繁體中文", "🦇", "last"];
    let variant = strings.to_variant();
    let iter = || variant.array_iter_str().unwrap();
    assert_eq!(iter().next(), Some("first"));
    assert_eq!(iter().nth(2), Some("繁體中文"));
    assert_eq!(iter().last(), Some("last"));
    assert_eq!(iter().next_back(), Some("last"));
    assert_eq!(iter().nth_back(1), Some("🦇"));
    assert_eq!(iter().collect::<Vec<_>>(), strings);
    assert_eq!(
        iter().rev().collect::<Vec<_>>(),
        strings.into_iter().rev().collect::<Vec<_>>()
    );
}

#[test]
fn mixed_iteration_and_exhaustion_preserve_bounds() {
    let variant = ["front", "middle", "back"].to_variant();
    let mut iter = variant.array_iter_str().unwrap();
    assert_eq!(iter.next(), Some("front"));
    assert_eq!(iter.next_back(), Some("back"));
    assert_eq!(iter.len(), 1);
    assert_eq!(iter.next_back(), Some("middle"));
    assert_eq!(iter.next(), None);
    assert_eq!(iter.next_back(), None);
    assert_eq!(iter.nth(usize::MAX), None);
    assert_eq!(iter.nth_back(usize::MAX), None);
    assert_eq!(iter.last(), None);

    let empty: [&str; 0] = [];
    let variant = empty.to_variant();
    assert_eq!(variant.array_iter_str().unwrap().next(), None);
    assert_eq!(variant.array_iter_str().unwrap().next_back(), None);
    assert_eq!(variant.array_iter_str().unwrap().last(), None);
}
