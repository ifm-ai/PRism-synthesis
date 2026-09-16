#!/bin/bash

# Recreate the /artifacts/evaluation/ layout that eval.sh was synthesized to expect.
# eval.sh was written inside the pipeline assuming these paths; we bridge them here.
mkdir -p /logs/verifier
mkdir -p /artifacts/evaluation

cp /tests/eval.sh /artifacts/evaluation/eval.sh

if [ -f /tests/test.patch ]; then
    cp /tests/test.patch /artifacts/evaluation/test.patch
fi

if [ -d /tests/tests ]; then
    cp -r /tests/tests /artifacts/evaluation/tests
fi

cd /workspace

# Run eval.sh — capture output regardless of exit code.
# eval.sh exits non-zero on test failure by design; || true prevents script abort.
EVAL_OUT=$(bash /artifacts/evaluation/eval.sh 2>&1) || true
echo "$EVAL_OUT"

# Parse OPENENV_EXIT_CODE — non-fatal: || true guards against grep/cut failure.
# If the marker is missing or malformed, EXIT_CODE is empty -> treated as failure.
EXIT_CODE=$(echo "$EVAL_OUT" | grep -o 'OPENENV_EXIT_CODE=[0-9]*' | tail -1 | cut -d= -f2 || true)

# Write reward: 1 only if marker is present and equals 0, else 0.
# Use explicit if/else — never rely on shell one-liner redirection.
if [ "$EXIT_CODE" = "0" ]; then
    echo "1" > /logs/verifier/reward.txt
else
    echo "0" > /logs/verifier/reward.txt
fi
