// Module file for hidden verifier tests

mod test_rpc_socket_dir;
mod test_logging_init;
// Note: test_rpc_invalid_rust_log_handling removed - not reliably testable
// in environments without journal access. The error goes to journal logger
// which may not output to stderr in test environments.
