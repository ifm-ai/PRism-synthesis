// SPDX-License-Identifier: Apache-2.0
// Hidden verifier test for bpfman socket directory creation
// This test verifies that the RPC binary creates socket directories on startup

use std::fs;
use std::path::Path;
use std::process::{Command, Stdio};
use std::time::Duration;

const RTDIR_SOCK: &str = "/run/bpfman-sock";

fn cleanup_dirs() {
    // Clean up socket directories before testing to ensure fresh state
    // Ignore errors if directories don't exist or aren't writable
    let _ = fs::remove_dir_all(RTDIR_SOCK);
    let _ = fs::remove_dir_all("/run/bpfman");
}

#[test]
fn test_rpc_creates_socket_directory() {
    // CRITICAL: Clean up any existing directories to ensure fresh state
    cleanup_dirs();
    // Small delay to ensure cleanup completes
    std::thread::sleep(Duration::from_millis(200));

    // Verify directories are cleaned up (best effort - may fail without root)
    // We proceed regardless because the key test is whether the binary creates them

    // The key behavioral difference:
    // BUGGY: main() calls serve() directly -> tries to bind immediately -> fails with
    //        "No such file or directory" because /run/bpfman-sock doesn't exist
    // FIXED: main() calls initialize_rpc() first -> creates /run/bpfman-sock -> then
    //        serve() can bind

    // Run bpfman-rpc without --help to trigger the actual main() code path
    let mut child = Command::new("/workspace/target/debug/bpfman-rpc")
        .env("RUST_LOG", "debug")
        .stderr(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .expect("Failed to spawn bpfman-rpc");

    // Give it a moment to either fail or start initializing
    std::thread::sleep(Duration::from_millis(500));

    // Check if the process exited early (buggy behavior)
    let _exited_early = child.try_wait().unwrap_or(None).is_some();

    // Kill the process to capture output
    let _ = child.kill();
    let output = child.wait_with_output().expect("Failed to get output");

    let stderr = String::from_utf8_lossy(&output.stderr);
    let stdout = String::from_utf8_lossy(&output.stdout);
    let combined_output = format!("{}{}", stdout, stderr);

    // The behavioral check:
    // BUGGY: Exits quickly with "No such file or directory" error
    // FIXED: Runs successfully (creates directory, binds to socket)

    let has_missing_dir_error = combined_output.contains("No such file or directory");

    // Additional check: did the directory get created?
    let sock_dir_exists = Path::new(RTDIR_SOCK).exists();

    // Clean up after test
    cleanup_dirs();

    // VERIFICATION LOGIC:
    // FIXED code: initialize_rpc() runs first, creates /run/bpfman-sock
    //             -> sock_dir_exists should be true
    //             -> no "No such file or directory" error
    // BUGGY code: serve() runs immediately, tries to bind before dir exists
    //             -> sock_dir_exists should be false
    //             -> sees "No such file or directory" error

    // Primary assertion: should NOT fail with missing directory error
    assert!(!has_missing_dir_error,
        "RPC should not fail with 'No such file or directory'. \
         initialize_rpc() creates /run/bpfman-sock before serve() tries to bind. \
         Buggy code calls serve() directly without directory creation. \
         stderr: {}, stdout: {}", stderr, stdout);

    // Secondary assertion: socket directory should be created
    assert!(sock_dir_exists,
        "Socket directory /run/bpfman-sock should be created by initialize_rpc(). \
         This is the key behavioral difference between buggy and fixed code.");
}

#[test]
fn test_rpc_creates_csi_directory_when_enabled() {
    // Clean up any existing directories
    cleanup_dirs();
    // Small delay to ensure cleanup completes
    std::thread::sleep(Duration::from_millis(200));

    // Run with CSI support enabled
    let mut child = Command::new("/workspace/target/debug/bpfman-rpc")
        .arg("--csi-support")
        .env("RUST_LOG", "debug")
        .stderr(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .expect("Failed to spawn bpfman-rpc with --csi-support");

    // Give it time to initialize
    std::thread::sleep(Duration::from_millis(500));

    // Kill and capture
    let _ = child.kill();
    let output = child.wait_with_output().expect("Failed to get output");
    let stderr = String::from_utf8_lossy(&output.stderr);
    let stdout = String::from_utf8_lossy(&output.stdout);
    let combined_output = format!("{}{}", stdout, stderr);

    // With --csi-support and the fix, /run/bpfman/csi should be created
    let csi_dir = "/run/bpfman/csi";
    let csi_dir_exists = Path::new(csi_dir).exists();

    // Check for errors
    let has_missing_dir_error = combined_output.contains("No such file or directory");

    // Clean up
    cleanup_dirs();

    assert!(!has_missing_dir_error,
        "RPC with --csi-support should not fail with 'No such file or directory'. \
         initialize_rpc() creates required directories. stderr: {}", stderr);

    assert!(csi_dir_exists,
        "CSI directory /run/bpfman/csi should be created when --csi-support is enabled. \
         initialize_rpc() creates both /run/bpfman-sock and /run/bpfman/csi (when --csi-support). \
         stderr: {}", stderr);
}
