import sys

_DEFAULT_CONTAINER_MEMORY = 2  # In GB, for the specifying the memory
_DEFAULT_CONTAINER_CORES = 2
_DEFAULT_ENV_FILE_MODE = 0o755
_CONCURRENT_TASKS = 1000
_DYNAMIC_CONCURRENT_WAIT_SEC = 60
_DEFAULT_MASTER_MONITOR_POOL_SEC = 15
_DEFAULT_EVENT_BUS_PORT= 8789
_DEFAULT_LLM_CONTEXT_LIMIT = 128_000
_UDF_WRAPPER = """
import cloudpickle
import os
import sys

def runner():
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    try:
        with open(input_path, "rb") as f:
            data = cloudpickle.load(f)
        
        func = data["func"]
        instruction = data["instruction"]
        
        result_val = func(instruction)
        
        with open(output_path, "wb") as f:
            result = {"status": 0, "result": result_val}
            cloudpickle.dump(result, f)

    except Exception as e:
        with open(output_path, "wb") as f:
            result = {"status": -1, "result": str(e)}
            cloudpickle.dump(result, f)

if __name__ == "__main__":
    runner()
"""

_DEFAULT_PACKAGE_IN_ENV_DIR = "/.environ"
_PACKAGE_ENV_SETUP = (
    "set -e;"
    # Ensure bash is available before anything else
    "if ! command -v bash >/dev/null 2>&1; then "
    "if command -v apt-get >/dev/null 2>&1; then apt-get update -qq || true && apt-get install -y bash -qq || true; "
    "elif command -v yum >/dev/null 2>&1; then yum install -y bash -q || true; "
    "elif command -v apk >/dev/null 2>&1; then apk add --no-cache bash || true; "
    "fi; fi;"
    # Detect package manager and install wget + curl
    "if command -v apt-get >/dev/null 2>&1; then "
    "apt-get update -qq || true && apt-get install -y wget curl -qq || true; "
    "elif command -v yum >/dev/null 2>&1; then "
    "yum install -y wget curl -q || true; "
    "elif command -v apk >/dev/null 2>&1; then "
    "apk add --no-cache wget curl || true; "
    "fi;"
    # Detect CPU architecture for the correct Miniconda installer
    "ARCH=$(uname -m);"
    "case $ARCH in aarch64) MCARCH=aarch64;; *) MCARCH=x86_64;; esac;"
    f"mkdir -p {_DEFAULT_PACKAGE_IN_ENV_DIR};"
    f"cd {_DEFAULT_PACKAGE_IN_ENV_DIR};"
    "wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-${MCARCH}.sh -O miniconda.sh "
    "|| curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-${MCARCH}.sh -o miniconda.sh;"
    "chmod +x miniconda.sh;"
    f"bash miniconda.sh -b -p {_DEFAULT_PACKAGE_IN_ENV_DIR}/miniconda;"
    f"source {_DEFAULT_PACKAGE_IN_ENV_DIR}/miniconda/bin/activate;"
    "conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main || true;"
    "conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r || true;"
    f"conda create -y -n venv python={sys.version_info.major}.{sys.version_info.minor} || true;"
    "conda activate venv;"
    "pip install --upgrade pip setuptools wheel cloudpickle boto3;"
    'echo "Virtual environment created at venv";'
)
_ENV_ENABLE_CMD = f"source {_DEFAULT_PACKAGE_IN_ENV_DIR}/miniconda/bin/activate && conda activate venv"
_JOB_SETUP_SCRIPT = (
    "base64 -d /job-config-mount/agentdist.whl.b64 > /tmp/{package_name};"
    "pip install /tmp/{package_name} -q;"
    'echo "agentdist environment ready";'
)
METRICS_FIELD_NAME = "_metrics_attributes"
