//! Hidden integration test for signature v component hex serialization.
//! This test verifies that the v field in signature JSON is hex-encoded (e.g., "0x1b")
//! rather than a plain integer (e.g., 27).
//!
//! Run with: cargo test --package alloy-primitives --features serde -- test_signature_v_hex

use alloy_primitives::{Signature, U256};
use std::str::FromStr;

/// Test that NonEip155 v values are serialized as hex strings.
/// The v component should appear as "0x1b" not 27 in JSON output.
/// Parity value 27 creates a NonEip155 variant which serializes as "v" field.
#[test]
fn test_v_serialization_is_hex() {
    // Create a signature with NonEip155 parity (v = 27 in legacy format)
    // Using parity value 27 gives us Parity::NonEip155(false) which should serialize as v=0x1b
    let signature = Signature::from_rs_and_parity(
        U256::from_str("0x3d43270611ffb1a10fcab841e636e355a787151969b920cf10fef48d3a61aac3").unwrap(),
        U256::from_str("0x11336489e3050e3ec017079dfe16582ce3d167559bcaa8383b665b3fda4eb963").unwrap(),
        27u64, // parity 27 -> Parity::NonEip155(false) -> v = 27 (0x1b) in NonEip155 mode
    ).unwrap();

    // Serialize to JSON
    let serialized = serde_json::to_string(&signature).unwrap();

    // The v field MUST be hex-encoded as "0x1b", not the integer 27
    // This is the core behavior being verified by the fix
    assert!(
        serialized.contains("\"v\":\"0x1b\""),
        "v field should be hex-encoded as \"0x1b\" but got: {}",
        serialized
    );

    // Also verify it does NOT contain the integer form
    assert!(
        !serialized.contains("\"v\":27"),
        "v field should NOT be plain integer 27 but got: {}",
        serialized
    );
}

/// Test roundtrip: serialize -> deserialize -> compare
/// This ensures both serialization and deserialization work correctly with hex v values.
#[test]
fn test_v_roundtrip() {
    // Original JSON with hex-encoded v (NonEip155 signature with v=27)
    let original_json = r#"{"r":"0x3d43270611ffb1a10fcab841e636e355a787151969b920cf10fef48d3a61aac3","s":"0x11336489e3050e3ec017079dfe16582ce3d167559bcaa8383b665b3fda4eb963","v":"0x1b"}"#;

    // Deserialize from JSON
    let sig: Signature = serde_json::from_str(original_json).unwrap();

    // Serialize back to JSON
    let reserialized = serde_json::to_string(&sig).unwrap();

    // Roundtrip should preserve the exact JSON representation
    assert_eq!(
        reserialized, original_json,
        "Roundtrip should preserve hex-encoded v field"
    );
}

/// Test tuple serialization also uses hex encoding for v
#[test]
fn test_tuple_v_hex() {
    // Create signature with NonEip155 parity (v=27)
    let signature = Signature::from_rs_and_parity(
        U256::from_str("0x3d43270611ffb1a10fcab841e636e355a787151969b920cf10fef48d3a61aac3").unwrap(),
        U256::from_str("0x11336489e3050e3ec017079dfe16582ce3d167559bcaa8383b665b3fda4eb963").unwrap(),
        27u64,
    ).unwrap();

    // Serialize to JSON (map format when human-readable)
    let serialized = serde_json::to_string(&signature).unwrap();

    // Should have hex-encoded v
    assert!(
        serialized.contains("\"v\":\"0x1b\""),
        "v field should be hex-encoded as \"0x1b\" but got: {}",
        serialized
    );
}

/// Test with v=28 (NonEip155 true) also produces hex output
#[test]
fn test_v28_serialization_is_hex() {
    let signature = Signature::from_rs_and_parity(
        U256::from_str("0x3d43270611ffb1a10fcab841e636e355a787151969b920cf10fef48d3a61aac3").unwrap(),
        U256::from_str("0x11336489e3050e3ec017079dfe16582ce3d167559bcaa8383b665b3fda4eb963").unwrap(),
        28u64, // parity 28 -> Parity::NonEip155(true) -> v = 28 (0x1c)
    ).unwrap();

    let serialized = serde_json::to_string(&signature).unwrap();

    // The v field MUST be hex-encoded as "0x1c", not the integer 28
    assert!(
        serialized.contains("\"v\":\"0x1c\""),
        "v field should be hex-encoded as \"0x1c\" but got: {}",
        serialized
    );

    assert!(
        !serialized.contains("\"v\":28"),
        "v field should NOT be plain integer 28 but got: {}",
        serialized
    );
}
