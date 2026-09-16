// Copyright (C) Copyright IBM Corp. 2024
//
// SPDX-License-Identifier: Apache-2.0
//
// Hidden tests for SE_SKIP_CERTS_VERIFICATION environment variable behavior
// These tests verify that the fix removes the #[cfg(debug_assertions)] guard
// around SE_SKIP_CERTS_VERIFICATION handling in deps/verifier/src/se/ibmse.rs.
//
// The fix.patch changes:
// - BEFORE: SE_SKIP_CERTS_VERIFICATION handling was ONLY present in debug builds
// - AFTER: SE_SKIP_CERTS_VERIFICATION handling is present in ALL builds
//
// This test verifies the source code structure to ensure the fix is applied.

use std::fs;
use std::path::Path;

/// The path to the ibmse.rs source file relative to /workspace
const IBMSE_RS_PATH: &str = "/workspace/deps/verifier/src/se/ibmse.rs";

/// Read the source file and return its content
fn read_source() -> String {
    let source_path = Path::new(IBMSE_RS_PATH);
    assert!(
        source_path.exists(),
        "Source file {} must exist for verification",
        IBMSE_RS_PATH
    );
    fs::read_to_string(source_path).expect("Failed to read ibmse.rs source file")
}

/// Test that verifies SE_SKIP_CERTS_VERIFICATION handling is NOT guarded by #[cfg(debug_assertions)]
///
/// This test:
/// 1. Reads the source file ibmse.rs
/// 2. Checks that DEFAULT_SE_SKIP_CERTS_VERIFICATION constant exists
/// 3. Verifies there is NO #[cfg(debug_assertions)] immediately before the constant
///
/// PASS condition (fixed code):
/// - The constant `const DEFAULT_SE_SKIP_CERTS_VERIFICATION: &str = "false";` exists
/// - It appears OUTSIDE any #[cfg(debug_assertions)] block (no such line immediately before it)
///
/// FAIL condition (buggy code):
/// - The constant appears immediately after `#[cfg(debug_assertions)]` and `{`
#[test]
#[cfg(feature = "se-verifier")]
fn test_se_skip_certs_verification_is_unconditional() {
    let source_content = read_source();
    let lines: Vec<&str> = source_content.lines().collect();

    // Find the line with DEFAULT_SE_SKIP_CERTS_VERIFICATION constant
    let mut const_line_idx: Option<usize> = None;
    for (i, line) in lines.iter().enumerate() {
        if line.contains("const DEFAULT_SE_SKIP_CERTS_VERIFICATION") && line.contains("const") {
            const_line_idx = Some(i);
            break;
        }
    }

    assert!(
        const_line_idx.is_some(),
        "DEFAULT_SE_SKIP_CERTS_VERIFICATION constant must be defined in ibmse.rs"
    );

    let const_idx = const_line_idx.unwrap();

    // Check the lines immediately before the constant
    // In buggy code: #[cfg(debug_assertions)] followed by { followed by const
    // In fixed code: no #[cfg(debug_assertions)] before the const

    // Look at up to 3 lines before the constant
    let start_check = if const_idx >= 3 { const_idx - 3 } else { 0 };
    let preceding_lines: Vec<&str> = lines[start_check..const_idx].to_vec();

    // Check if any preceding line contains #[cfg(debug_assertions)]
    for line in &preceding_lines {
        let trimmed = line.trim();
        assert!(
            !trimmed.starts_with("#[cfg(debug_assertions)]"),
            "DEFAULT_SE_SKIP_CERTS_VERIFICATION must NOT be inside #[cfg(debug_assertions)] block. \
             Found #[cfg(debug_assertions)] at line {}: '{}'. \
             The fix.patch removes this debug-only guard.",
            start_check + preceding_lines.iter().position(|&l| l == *line).unwrap() + 1,
            trimmed
        );
    }

    // Also verify the constant is not preceded by just an opening brace
    // (which would be the opening of the cfg block)
    if const_idx > 0 {
        let prev_line = lines[const_idx - 1].trim();
        // It's okay if the previous line is empty or a comment, but not an opening brace
        // from a cfg block
        if const_idx >= 2 {
            let two_lines_before = lines[const_idx - 2].trim();
            if two_lines_before.starts_with("#[cfg(debug_assertions)]") {
                panic!(
                    "DEFAULT_SE_SKIP_CERTS_VERIFICATION is inside #[cfg(debug_assertions)] block. \
                     Line {}: '{}', Line {}: '{}', Line {}: '{}'. \
                     The fix must remove this guard.",
                    const_idx - 1,
                    two_lines_before,
                    const_idx,
                    prev_line,
                    const_idx + 1,
                    lines[const_idx].trim()
                );
            }
        }
    }
}

/// Test that there is NO #[cfg(not(debug_assertions))] block in the certificate verification area
///
/// Buggy code has two separate blocks:
/// - #[cfg(debug_assertions)] with skip_certs check
/// - #[cfg(not(debug_assertions))] without skip_certs check
///
/// Fixed code has NO such cfg blocks - just one unconditional block
#[test]
#[cfg(feature = "se-verifier")]
fn test_no_cfg_not_debug_assertions_in_verification() {
    let source_content = read_source();
    let lines: Vec<&str> = source_content.lines().collect();

    // Look for any #[cfg(not(debug_assertions))] in the file
    // In fixed code, this should not exist at all
    for (i, line) in lines.iter().enumerate() {
        let trimmed = line.trim();
        if trimmed.starts_with("#[cfg(not(debug_assertions))]") {
            panic!(
                "Found #[cfg(not(debug_assertions))] at line {}. \
                 The fix.patch removes both #[cfg(debug_assertions)] and #[cfg(not(debug_assertions))] \
                 blocks, replacing them with a single unconditional block.",
                i + 1
            );
        }
    }
}

/// Test that the fix results in a single unconditional certificate verification block
/// with the skip_certs check
///
/// This verifies the key behavioral change:
/// - Fixed code: `if !skip_certs {{` appears unconditionally before CertVerifier::new
/// - Buggy code: CertVerifier::new appears both inside and outside skip_certs check
#[test]
#[cfg(feature = "se-verifier")]
fn test_certificate_verification_uses_skip_certs_unconditionally() {
    let source_content = read_source();
    let lines: Vec<&str> = source_content.lines().collect();

    // Find all occurrences of "if !skip_certs {"
    let mut skip_check_lines: Vec<usize> = Vec::new();
    for (i, line) in lines.iter().enumerate() {
        if line.trim() == "if !skip_certs {" {
            skip_check_lines.push(i);
        }
    }

    assert!(
        !skip_check_lines.is_empty(),
        "Expected at least one 'if !skip_certs {{' for conditional certificate verification"
    );

    // Find all occurrences of "CertVerifier::new"
    let mut cert_verifier_lines: Vec<usize> = Vec::new();
    for (i, line) in lines.iter().enumerate() {
        if line.contains("CertVerifier::new") {
            cert_verifier_lines.push(i);
        }
    }

    assert!(
        !cert_verifier_lines.is_empty(),
        "Expected at least one CertVerifier::new call"
    );

    // In fixed code, ALL CertVerifier::new calls should be inside an "if !skip_certs {" block
    // We check that each CertVerifier::new appears after an "if !skip_certs {" without
    // an intervening closing brace

    for &cert_line in &cert_verifier_lines {
        let mut found_skip_check_before = false;

        // Look backwards from CertVerifier::new to find the nearest control structure
        for i in (0..cert_line).rev() {
            let line = lines[i].trim();

            if line == "if !skip_certs {" {
                found_skip_check_before = true;
                break;
            }

            // If we hit a function definition or impl block start, stop looking
            if line.starts_with("fn ") || line.starts_with("pub fn ") ||
               line.starts_with("impl ") || line.starts_with("struct ") {
                break;
            }

            // If we hit a standalone closing brace (end of some block), stop
            // This is a simplification - in practice we'd need full brace matching
            if line == "}" && i > 0 && lines[i - 1].trim().ends_with(")?;") {
                // This is likely the end of verifier.verify(c)?; which means
                // we're already inside a block
                break;
            }
        }

        assert!(
            found_skip_check_before,
            "CertVerifier::new at line {} must be inside an 'if !skip_certs {{' block. \
             In fixed code, certificate verification is ALWAYS conditional on skip_certs.",
            cert_line + 1
        );
    }
}

/// Test that verifies the overall structure matches the fixed pattern
///
/// The fix.patch transforms:
/// ```
/// #[cfg(debug_assertions)]
/// {
///     const DEFAULT_SE_SKIP_CERTS_VERIFICATION: &str = "false";
///     let skip_certs_env = env_or_default!(...);
///     let skip_certs: bool = ...;
///     if !skip_certs { verifier.verify(c)?; }
/// }
/// #[cfg(not(debug_assertions))]
/// {
///     let verifier = CertVerifier::new(...);
///     verifier.verify(c)?;
/// }
/// ```
///
/// Into:
/// ```
/// const DEFAULT_SE_SKIP_CERTS_VERIFICATION: &str = "false";
/// let skip_certs_env = env_or_default!(...);
/// let skip_certs: bool = ...;
/// if !skip_certs {
///     let verifier = CertVerifier::new(...);
///     verifier.verify(c)?;
/// }
/// ```
#[test]
#[cfg(feature = "se-verifier")]
fn test_fix_pattern_matches_expected_structure() {
    let source_content = read_source();

    // The fixed code should have these patterns in sequence (not separated by cfg blocks):
    // 1. const DEFAULT_SE_SKIP_CERTS_VERIFICATION
    // 2. env_or_default! with SE_SKIP_CERTS_VERIFICATION
    // 3. skip_certs parsing
    // 4. if !skip_certs { ... CertVerifier::new ... }

    assert!(
        source_content.contains("const DEFAULT_SE_SKIP_CERTS_VERIFICATION: &str = \"false\";"),
        "Must have DEFAULT_SE_SKIP_CERTS_VERIFICATION constant"
    );

    assert!(
        source_content.contains("env_or_default!") && source_content.contains("SE_SKIP_CERTS_VERIFICATION"),
        "Must have env_or_default! call for SE_SKIP_CERTS_VERIFICATION"
    );

    assert!(
        source_content.contains("if !skip_certs {"),
        "Must have 'if !skip_certs {{' conditional"
    );

    // Critical: the file should NOT contain #[cfg(debug_assertions)] or #[cfg(not(debug_assertions))]
    // in the context of SE_SKIP_CERTS_VERIFICATION or certificate verification
    assert!(
        !source_content.contains("#[cfg(debug_assertions)]"),
        "Fixed code must NOT contain #[cfg(debug_assertions)] - the guard must be removed"
    );

    assert!(
        !source_content.contains("#[cfg(not(debug_assertions))]"),
        "Fixed code must NOT contain #[cfg(not(debug_assertions))] - replaced with unconditional code"
    );
}
