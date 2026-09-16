// SPDX-License-Identifier: Apache-2.0
// Hidden verifier test for bpfman logging initialization
// This test verifies that logging is properly initialized in RPC and CLI binaries

use std::env;
use std::process::{Command, Stdio};
use std::time::Duration;

#[test]
fn test_cli_logging_initialization() {
    // The fix adds env_logger::try_init() and debug! logging to the CLI binary main()
    // We verify this by running the CLI with RUST_LOG=debug and checking for the
    // "Log using env_logger" debug message that appears BEFORE the help output.
    //
    // BUGGY: main() goes straight to clap::parse() -> shows help without logging init
    // FIXED: main() calls env_logger::try_init() first -> debug message appears

    // Clean environment
    env::remove_var("RUST_LOG");

    // Run bpfman CLI with RUST_LOG=debug
    // Running without args shows help but the fix logs BEFORE clap parsing
    let output = Command::new("/workspace/target/debug/bpfman")
        .env("RUST_LOG", "debug")
        .stderr(Stdio::piped())
        .stdout(Stdio::piped())
        .output()
        .expect("Failed to execute bpfman");

    let stderr = String::from_utf8_lossy(&output.stderr);
    let stdout = String::from_utf8_lossy(&output.stdout);
    let combined_output = format!("{}{}", stdout, stderr);

    // The fix adds: debug!("Log using env_logger");
    // This should appear in stderr when RUST_LOG=debug is set
    let has_debug_log = combined_output.contains("Log using env_logger");

    assert!(has_debug_log,
        "CLI should output 'Log using env_logger' debug message when RUST_LOG=debug is set. \
         This message is only printed if env_logger::try_init() is called in main() BEFORE \
         clap parsing. Buggy code shows help without logging init. \
         stderr: {}, stdout: {}", stderr, stdout);
}

#[test]
fn test_rpc_logging_initialization() {
    // The fix adds logging initialization to RPC binary:
    // - JournalLog if connected to journal
    // - env_logger fallback otherwise
    //
    // We verify by running the RPC and checking for logging output.
    //
    // BUGGY: main() calls serve() directly -> no logging init -> fails on socket bind
    // FIXED: main() calls initialize_rpc() first -> logging init -> can bind to socket

    // Clean up first to ensure we test directory creation
    let _ = std::fs::remove_dir_all("/run/bpfman-sock");
    let _ = std::fs::remove_dir_all("/run/bpfman");

    // Run bpfman-rpc to trigger actual main() execution
    let mut child = Command::new("/workspace/target/debug/bpfman-rpc")
        .env("RUST_LOG", "debug")
        .stderr(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .expect("Failed to spawn bpfman-rpc");

    // Give it time to initialize logging and start the server
    std::thread::sleep(Duration::from_millis(500));

    // Kill and capture output
    let _ = child.kill();
    let output = child.wait_with_output().expect("Failed to get output");
    let stderr = String::from_utf8_lossy(&output.stderr);
    let stdout = String::from_utf8_lossy(&output.stdout);
    let combined_output = format!("{}{}", stdout, stderr);

    // Check for "No such file or directory" error (buggy behavior)
    let has_missing_dir_error = combined_output.contains("No such file or directory");

    // The fix adds either:
    // - debug!("Log using journald"); if connected to journal
    // - debug!("Log using env_logger"); as fallback

    let has_journald_log = combined_output.contains("Log using journald");
    let has_env_logger_log = combined_output.contains("Log using env_logger");
    let has_logging_init = has_journald_log || has_env_logger_log;

    // Check for panics
    let has_panic = stderr.contains("panic") || stderr.contains("thread 'main' panicked");

    assert!(!has_panic, "RPC logging initialization should not panic. stderr: {}", stderr);

    // Should not fail with missing directory error
    assert!(!has_missing_dir_error,
        "RPC should not fail with 'No such file or directory'. \
         initialize_rpc() creates the directory before serve() tries to bind. \
         stderr: {}", stderr);

    // Should have logging output
    assert!(has_logging_init,
        "RPC should output either 'Log using journald' or 'Log using env_logger' when RUST_LOG=debug is set. \
         This message is only printed if initialize_rpc() is called in main(), which sets up logging. \
         Buggy code calls serve() directly without logging init. \
         stderr: {}, stdout: {}", stderr, stdout);
}

#[test]
fn test_rpc_socket_dir_creation_evidence() {
    // This test provides additional evidence that initialize_rpc() is being called
    // by checking that the server can start without immediate socket errors.
    //
    // BUGGY: serve() called directly -> tries to bind to /run/bpfman-sock/bpfman.sock
    //        -> if directory doesn't exist, fails with "No such file or directory"
    // FIXED: initialize_rpc() called first -> creates /run/bpfman-sock -> serve() can bind

    // Clean up first
    let _ = std::fs::remove_dir_all("/run/bpfman-sock");
    let _ = std::fs::remove_dir_all("/run/bpfman");

    // Run bpfman-rpc and capture output
    let mut child = Command::new("/workspace/target/debug/bpfman-rpc")
        .env("RUST_LOG", "info")
        .stderr(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .expect("Failed to spawn bpfman-rpc");

    // Give it time to either fail or start
    std::thread::sleep(Duration::from_millis(500));

    // Check if still running (fixed code should be running)
    let is_running = child.try_wait().unwrap_or(None).is_none();

    // Kill and capture
    let _ = child.kill();
    let output = child.wait_with_output().expect("Failed to get output");
    let stderr = String::from_utf8_lossy(&output.stderr);

    // Check for "No such file or directory" error on socket bind
    let has_missing_dir_error = stderr.contains("No such file or directory")
        && (stderr.contains("bpfman-sock") || stderr.contains("socket"));

    // Clean up
    let _ = std::fs::remove_dir_all("/run/bpfman-sock");
    let _ = std::fs::remove_dir_all("/run/bpfman");

    // FIXED: Should be running (directory created) and no missing dir error
    // BUGGY: May have exited with missing dir error
    assert!(!has_missing_dir_error,
        "RPC should not fail with 'No such file or directory' on socket bind. \
         initialize_rpc() creates the directory before serve() tries to bind. \
         stderr: {}", stderr);

    // The server should be able to start
    assert!(is_running,
        "RPC server should still be running after 500ms. \
         Buggy code exits immediately due to socket bind failure. \
         stderr: {}", stderr);
}
