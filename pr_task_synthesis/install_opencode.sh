#!/bin/bash
set -euo pipefail
ARTIFACTS=/.download_artifacts

# --- Detect arch (mirrors install.sh) ---
arch=$(uname -m)
[ "$arch" = "x86_64" ] && arch="x64"
[ "$arch" = "aarch64" ] && arch="arm64"

# --- Detect musl libc (Alpine or musl ldd) ---
is_musl=false
[ -f /etc/alpine-release ] && is_musl=true
if command -v ldd >/dev/null 2>&1 && ldd --version 2>&1 | grep -qi musl; then is_musl=true; fi

# --- Detect AVX2 (x64 only; older CPUs need -baseline build) ---
needs_baseline=false
if [ "$arch" = "x64" ] && ! grep -qwi avx2 /proc/cpuinfo 2>/dev/null; then needs_baseline=true; fi

# --- Build target string ---
target="linux-${arch}"
[ "$needs_baseline" = "true" ] && target="${target}-baseline"
[ "$is_musl" = "true" ]        && target="${target}-musl"

tarball="${ARTIFACTS}/opencode-${target}.tar.gz"
echo "Detected target: ${target}, tarball: ${tarball}"
if [ ! -f "$tarball" ]; then
    echo "ERROR: tarball not found: ${tarball}"
    ls -la "${ARTIFACTS}/" || true
    exit 1
fi

# --- Extract binary and install (mirrors install.sh install_from_binary: cp + chmod) ---
tmpdir=$(mktemp -d)
tar -xzf "$tarball" -C "$tmpdir"
mkdir -p $HOME/.opencode/bin
cp "$tmpdir/opencode" $HOME/.opencode/bin/opencode
chmod 755 $HOME/.opencode/bin/opencode
rm -rf "$tmpdir"

# --- Symlink to a stable PATH location ---
ln -sf $HOME/.opencode/bin/opencode /usr/local/bin/opencode
echo "opencode installed: $(%HOME/.opencode/bin/opencode --version 2>/dev/null || echo unknown)"
