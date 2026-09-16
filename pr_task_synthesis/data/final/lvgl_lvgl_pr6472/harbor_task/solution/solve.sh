#!/bin/bash
set -e
cd /workspace
git apply --whitespace=nowarn /solution/fix.patch
