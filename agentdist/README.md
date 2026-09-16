# agentdist


# agentdist

`agentdist` is a Python library for running agents and user-defined functions (UDFs) in a distributed, scalable manner. It provides a map-reduce-style programming interface to define and execute complex multi-stage workflows across different execution backends — from local subprocesses to container sandbox.

---

## Table of Contents

1. [Installation](#installation)
2. [Core Concepts](#core-concepts)
3. [Architecture](#architecture)
4. [AgentFlowContext](#agentflowcontext)
5. [DataObject](#dataobject)
6. [map() Operation](#map-operation)
7. [save() Operation](#save-operation)
8. [@udf() Decorator](#udf-decorator)
9. [AgentConfig](#agentconfig)
10. [Custom Agents](#custom-agents)
11. [Execution Backends](#execution-backends)
12. [Full Examples](#full-examples)

---

## Installation

```bash
pip install agentdist
# or from source:
pip install -e agent-dist/agentdist
```

---

## Core Concepts

| Concept | Description |
|---|---|
| `AgentFlowContext` | Entry point for single-node (local/docker) DAG execution |
| `DataObject` | Lazy, chainable representation of a distributed dataset (similar to a Spark RDD) |
| `.map()` | Apply a function or agent to every item in a `DataObject`; returns a new `DataObject` |
| `.save()` | Persist results to disk or S3; also chainable |
| `@udf()` | Decorator that serializes a Python function for execution in a remote environment |
| `AgentConfig` | Configuration for running a coding agent (opencode, forgecode) in a container |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  User Code                                                              │
│                                                                         │
│  context = AgentFlowContext.builder.app_name("my-app").build()          │
│  dag = context.from_stream(my_udf)                                      │
│             .map(agent_config, instruction=make_instruction)            │
│             .save(target_path="/results", custom_func=upload_to_s3)     │
│  dag.execute()                                                          │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  Orchestrator (agentdist core)                                            │
│                                                                           │
│  1. Walk parent chain  →  Build stage queue                               │
│  2. Group non-isolated operations into stages                             │
│  3. For each stage: stream items through with concurrency semaphore       │
│  4. For isolated operations: create executor, upload artifacts, exec      │
│  5. Collect TaskResult per item; pass to next stage                       │
└──────┬────────────────────────┬────────────────────────┬──────────────────┘
       │                        │                        │
       ▼                        ▼                        ▼
  LocalExecutor          DockerExecutor         ApptainerExecutor
  (subprocess)           (docker run)           (apptainer exec)
```

### Stage Groups and Isolation

The orchestrator groups consecutive non-isolated operations into a single stage. When an
operation requires an isolated environment (e.g., runs inside a container), it forms its
own stage group. This allows reuse of a single container across multiple chained `.map()`
calls that share the same environment.

```
from_stream()  →  [stage 0]  map(udf_local)       (non-isolated, local)
               →  [stage 1]  map(agent_config)    (isolated, K8s pod)
               →  [stage 1]  save(...)             (same pod, no new container)
```

---

## AgentFlowContext

`AgentFlowContext` is the entry point for building and executing a DAG locally or on a
single node. It owns the `Orchestrator` and manages concurrent task execution.

### Builder

```python
from agentdist.agentdist import AgentFlowContext

context = (
    AgentFlowContext.builder
    .app_name("my-app")                          # required
    .config("concurrent_tasks", 50)              # max parallel tasks
    .config("eager_stage_cleanup", True)         # destroy executor between stages
    .config("skip_env_setup", False)             # skip conda env setup
    .config("offload_executor", True)            # offload isolated ops to K8s jobs
    .config("telemetry.exporter_type", "otlp,console")
    .config("telemetry.exporter_endpoint", "http://otel-collector:4317")
    .build()
)
```

### Configuration Options

| Key | Default | Description |
|---|---|---|
| `concurrent_tasks` | 1000 | Semaphore limit — max items processed in parallel |
| `eager_stage_cleanup` | `False` | Destroy executor after each stage completes |
| `skip_env_setup` | `False` | Skip conda/virtualenv setup inside containers |
| `offload_executor` | `True` | Serialize isolated ops as K8s Jobs instead of inline execution |
| `telemetry.exporter_type` | `None` | Comma-separated: `otlp`, `console` |
| `telemetry.exporter_endpoint` | `None` | OTLP collector URL |
| `telemetry.metrics_file` | `None` | Local file for metrics export |
| `telemetry.export_interval_millis` | `30000` | Telemetry flush interval |

### Data Sources

```python
# From a Python list — each item becomes a TaskResult
data_object = context.from_pylist([item1, item2, item3])

# From a streaming UDF — function is called to yield items lazily
data_object = context.from_stream(my_streamer_udf)
```

---

## DataObject

`DataObject` is the central lazy data structure in agentdist. It represents a distributed
dataset and the transformations applied to it. Nothing executes until `.execute()` is
called — the chain of `.map()` and `.save()` calls only builds a DAG.

### Properties

```python
class DataObject:
    parent: DataObject | None       # Previous stage (builds the DAG chain)
    type: DataObjectTypes           # READ | STREAM | MAP
    operation: str                  # "pyread" | "stream" | "map" | "save"
    config: DataObjectConfig | None # UDF/agent config for this stage
    stage: Stage | None             # Results after execution
    isolate: bool                   # Whether this op needs its own executor
    save_failed: bool               # Whether to save even on failure
```

### DataObjectTypes

| Type | Created By | Description |
|---|---|---|
| `READ` | `context.from_pylist()` | Static list loaded into memory |
| `STREAM` | `context.from_stream()` | Lazily streamed via a UDF generator |
| `MAP` | `.map()` or `.save()` | Applied transformation |

### Execution

```python
dag.execute()
# Internally: context.execute(dag) → orchestrator.run_job(dag)
# Walks parent chain → builds ordered stage list → runs each stage
```

After execution, results are accessible via:

```python
dag.stage.results        # List[TaskResult] — successful items
dag.stage.failed_tasks   # List[TaskResult] — failed items
```

---

## map() Operation

`.map()` is the primary transformation method. It applies a function or agent to each
item in a `DataObject` and returns a new `DataObject` representing the transformed dataset.

### Signature

```python
def map(
    self,
    func: AgentConfig
         | UDFConfig
         | Callable[[TaskContext], AgentConfig | UDFConfig],
    instruction: Callable[[TaskContext], str] | str | None = None,
    parser: Callable[[TaskResult], Any] | None = None,
    isolate: bool = False,
    prev_operation_env_cleanup: bool = False,
    artifacts: List[str]
              | Callable[[TaskContext], Iterable[tuple[str, str]]]
              | None = None,
) -> DataObject
```

### Parameters

**`func`** — what to execute for each item:

```python
# Static AgentConfig — same config for every task
result = dag.map(func=my_agent_config)

# Static UDF — same function for every task
result = dag.map(func=my_udf)

# Dynamic factory — config built from the task's data
def make_config(task_context: TaskContext) -> AgentConfig:
    data = task_context.data.metadata["data"]
    return AgentConfig(
        backend="kubernetes",
        backend_config=KubernetesExecConfig(image=data["image"], ...),
        ...
    )
result = dag.map(func=make_config)
```

**`instruction`** — input passed to the function/agent:

```python
# Static string
result = dag.map(func=agent, instruction="Fix the bug in this repository.")

# Dynamic — computed from each item's data
result = dag.map(
    func=agent,
    instruction=lambda ctx: ctx.data.metadata["data"]["task_description"]
)
```

**`artifacts`** — files to upload into the execution environment before the function runs:

```python
# Static list of file paths
result = dag.map(func=agent, artifacts=["/local/file.json"])

# Dynamic generator — yields (container_path, local_path) tuples per task
def get_artifacts(task_context: TaskContext):
    data = task_context.data.metadata["data"]
    yield ("/tasks/config.json", "/local/config.json")
    if data.get("fix_patch"):
        yield ("/tasks/fix.patch", "/tmp/fix.patch")

result = dag.map(func=agent, artifacts=get_artifacts)
```

**`parser`** — transforms task output before passing it to the next stage:

```python
def extract_score(result: TaskResult) -> dict:
    return {"score": int(result.raw_output.strip()), "id": result.metadata["id"]}

result = dag.map(func=verifier_udf, parser=extract_score)
# Next stage receives {"score": ..., "id": ...} as its input
```

**`isolate`** — whether to run in a dedicated container:

```python
# isolate=False (default): share the executor from the previous stage
result = dag.map(func=lightweight_udf)

# isolate=True: always create a fresh container for this operation
result = dag.map(func=heavy_agent, isolate=True)

# Note: isolate is automatically True when func has a backend_config
```

**`prev_operation_env_cleanup`** — destroy the previous stage's executor before starting:

```python
result = dag.map(func=next_udf, prev_operation_env_cleanup=True)
```

### Chaining

`.map()` returns a new `DataObject` each time, so operations chain naturally:

```python
dag = (
    context.from_stream(load_tasks)
    .map(func=make_agent_config, instruction=make_instruction, artifacts=get_artifacts)
    .save(target_path="s3://bucket/results", custom_func=upload_to_s3)
    .map(func=verify_udf)
)
dag.execute()
```

---

## save() Operation

`.save()` is a special `.map()` that persists each task's working directory. It is
chainable — stages after `.save()` run in the same container.

### Signature

```python
def save(
    self,
    target_path: str,
    save_failed: bool = False,
    custom_func: Callable[[str, str], None] | None = None,
) -> DataObject
```

### Parameters

| Parameter | Description |
|---|---|
| `target_path` | Destination path prefix for saved results |
| `save_failed` | If `True`, save even when the previous stage returned an error |
| `custom_func` | Override the default `shutil.copytree` with a custom save function |

### Default Behavior

Without `custom_func`, each task's working directory is copied to
`<target_path>/<task_dir_name>/`.

### Custom Save (e.g., upload to S3)

```python
import boto3
from functools import partial

def upload_to_s3(bucket_name: str, task_dir: str, target_path: str):
    s3 = boto3.client("s3")
    for file_path in Path(task_dir).rglob("*"):
        if file_path.is_file():
            s3_key = f"{target_path}/{Path(task_dir).name}/{file_path.relative_to(task_dir)}"
            s3.upload_file(str(file_path), bucket_name, s3_key)

result = dag.map(func=agent).save(
    target_path="agent_results/my-run",
    save_failed=True,
    custom_func=partial(upload_to_s3, "my-bucket"),
)
```

---

## @udf() Decorator

The `@udf()` decorator wraps a Python function so it can be serialized and executed in
a remote environment (docker container, K8s pod, etc.). The decorated function is not
called directly — it returns a `UDFConfig` object that the orchestrator uses.

### Basic Usage

```python
from agentdist.orchestrator.udf import udf

@udf()
def process_item(item: str, state, **kwargs) -> str:
    # item: the instruction value from map(instruction=...)
    # state: State object (or None) for tracking processed items
    return f"Processed: {item}"
```

### Generator UDF (Streaming)

When the UDF is a generator, it can yield multiple items from a single input. This is
used to fan out one batch entry into many individual task records:

```python
@udf()
def stream_tasks(item: str, state, **kwargs):
    import json
    paths = json.loads(item)
    for path in paths:
        records = query_parquet(path)  # e.g., DataFusion query
        for record in records:
            if state and state.contains(record):
                continue
            yield record
```

### UDF with Isolated Environment

```python
from agentdist.structures.dataobject import RunTimeConfig
from agentdist.structures.executor import KubernetesExecConfig

@udf(env=RunTimeConfig(
    backend="kubernetes",
    backend_config=KubernetesExecConfig(
        name="my-udf-env",
        image="python:3.11",
        namespace="default",
    )
))
def heavy_computation(item: str, state, **kwargs):
    # Runs inside a K8s pod
    import pandas as pd
    return compute(item)
```

### UDF Parameter Signature

UDFs used in `.map()` receive:

```python
def my_udf(item: str, state: State | None, **kwargs):
    # item   — the resolved instruction string (from map(instruction=...))
    # state  — State object if AgentFlowJobContext was given a state; else None
    # kwargs — future extensibility
    ...
```

### How Serialization Works

When `@udf()` is applied, `get_function_schema()` captures:
- The function's source code
- All imports used inside the function
- Closure variables

This serialized bundle is sent to the remote environment, unpickled, and executed there.
All imports inside the UDF body must be available in the remote container's image.

---

## AgentConfig

`AgentConfig` configures how a coding agent (e.g., opencode) is run inside a container.

### Structure

```python
from agentdist.structures.agent import AgentConfig
from agentdist.structures.executor import KubernetesExecConfig

AgentConfig(
    name="opencode-agent",           # Identifier string
    agent="opencode",                # Agent binary: "opencode" 
    backend="apptainer",            # Execution backend
    backend_config=ContainerExecConfig(
        name="my-task-env",
        image="my-registry/sandbox:latest",
        post_setup_commands=[
            "git clone --depth 1 https://github.com/org/repo /workspace",
            "cd /workspace && pip install -e .",
        ],
        env_vars={
            "OPENCODE_CONFIG_CONTENT": json.dumps(opencode_config),
            "DEBIAN_FRONTEND": "noninteractive",
        },
       
    ),
    run_dir="/workspace",            # Working directory for the agent
    skip_setup=False,                # If True, skip conda/venv setup
    agent_run_timeout=4500,          # Max agent runtime in seconds
)
```

### Dynamic AgentConfig via Factory

When agent configuration depends on each task's data, use a factory function:

```python
def make_agent_config(task_context: TaskContext) -> AgentConfig:
    data = task_context.data.metadata["data"]
    return AgentConfig(
        name="opencode-agent",
        agent="opencode",
        backend="kubernetes",
        backend_config=KubernetesExecConfig(
            name=f"task_{data['task_id']}",
            image=data.get("custom_image", DEFAULT_IMAGE),
            post_setup_commands=build_setup_commands(data),
            env_vars=build_env_vars(data),
            ...
        ),
        run_dir=data.get("workdir", "/workspace"),
    )

result = dag.map(func=make_agent_config, instruction=make_instruction)
```

### Custom Agents

`AgentConfig.agent` is not limited to the built-in `"opencode"` strings.
You can pass **any class** that implements the `Agent` protocol from
`agentdist.agents.protocol`. The orchestrator instantiates it at runtime with the
executor and config, calls `setup()` to prepare the environment, then calls `run()` with
the instruction.

#### Agent Protocol

```python
# agentdist/agents/protocol.py
from agentdist.executors import ExecutionBackend
from agentdist.structures.agent import AgentContext, AgentConfig

class Agent(Protocol):
    def __init__(self, exec: ExecutionBackend, agent_config: AgentConfig) -> None:
        """Receive the active executor (container/pod) and the agent config."""

    async def setup(self):
        """Install or configure the agent inside the executor environment."""

    async def run(self, instruction: str, context: AgentContext):
        """Execute the agent with the given instruction; return AgentResult."""
```

#### Implementing a Custom Agent

```python
from agentdist.agents.protocol import Agent
from agentdist.executors import ExecutionBackend
from agentdist.structures.agent import AgentContext, AgentCoreConfig, AgentResult

class MyCustomAgent(Agent):
    """Example: wraps a custom CLI tool called `my-solver`."""

    def __init__(self, exec: ExecutionBackend, agent_config: AgentCoreConfig) -> None:
        self._sandbox = exec
        self._config = agent_config

    async def setup(self):
        """Install my-solver inside the container (skipped if already baked in image)."""
        if self._config.skip_setup:
            return
        result = await self._sandbox.exec(["pip", "install", "my-solver"])
        if result.return_code != 0:
            raise RuntimeError(f"my-solver install failed: {result.stderr}")

    async def run(self, instruction: str, context: AgentContext) -> AgentResult:
        """Write the instruction to a file and run my-solver against it."""
        import shlex

        # Write the instruction into the task directory
        await self._sandbox.exec([
            "bash", "-c",
            f"echo {shlex.quote(instruction)} > {context.task_dir}/task.md"
        ])

        # Run the solver
        result = await self._sandbox.exec(
            ["my-solver", "--task", f"{context.task_dir}/task.md",
             "--output", f"{context.task_dir}/solution.patch"],
            cwd=context.run_dir,
            timeout=self._config.run_timeout,
        )

        return AgentResult(
            status=result.return_code,
            stdout=result.stdout,
            stderr=result.stderr,
            trajectory=None,   # Populate AgentTrajectory if your tool produces one
        )
```

#### Using a Custom Agent in AgentConfig

Pass the **class itself** (not an instance) to the `agent` parameter:

```python
from agentdist.structures.agent import AgentConfig
from agentdist.structures.executor import KubernetesExecConfig

agent_config = AgentConfig(
    name="my-custom-agent",
    agent=MyCustomAgent,          # <-- class reference, not a string
    backend="apptainer",
    backend_config=ContainerExecConfig(
        name="my-solver-env",
        image="my-registry/my-solver:latest",
    ),
    run_dir="/workspace",
    agent_run_timeout=3600,
    skip_setup=True,              # skip setup() if the image already has my-solver
)

result = dag.map(func=agent_config, instruction=lambda ctx: ctx.data.metadata["data"]["task"])
```

The orchestrator detects that `agent` is a class (not a registered string like
`"opencode"`), instantiates it with the active executor, and dispatches `setup()` then
`run()` in the same way as built-in agents.

---

## Execution Backends

agentdist supports four execution backends. The backend is selected by the `backend`
field of `AgentConfig` or the `RunTimeConfig` inside a `@udf()`.

### Local

Runs commands as subprocesses on the current machine. No container isolation.

```python
from agentdist.structures.executor import ExecConfig

AgentConfig(
    backend="local",
    backend_config=ExecConfig(),
    ...
)
```

### Docker

Runs each task in a Docker container. The container is started, commands are executed
inside it via `docker exec`, and it is stopped after the task completes.

```python
from agentdist.structures.executor import ContainerExecConfig

AgentConfig(
    backend="docker",
    backend_config=ContainerExecConfig(
        name="my-docker-env",
        image="ubuntu:22.04",
        post_setup_commands=["apt-get install -y python3"],
        env_vars={"MY_VAR": "value"},
    ),
    ...
)
```

### Apptainer (Singularity)

Runs tasks inside an Apptainer (formerly Singularity) container. Useful on HPC clusters
where Docker is not available. Supports `secure=True` for rootless execution.

```python
from agentdist.structures.executor import ContainerExecConfig

AgentConfig(
    backend="apptainer",
    backend_config=ContainerExecConfig(
        name="my-apptainer-env",
        image="/path/to/sandbox.sif",
        secure=True,                 # Runs with unshare -r (rootless)
        storage_mounts={
            "/path/on/host/data": "/mnt",
        },
        post_setup_commands=["bash /tasks/setup.sh"],
        env_vars={"DEBIAN_FRONTEND": "noninteractive"},
    ),
    ...
)
```
---

## Full Examples

### Example 1: Local UDF Execution

```python
from agentdist.agentdist import AgentFlowContext
from agentdist.orchestrator.udf import udf

@udf()
def process(item: str, state, **kwargs) -> str:
    return f"Result: {item.upper()}"

context = AgentFlowContext.builder.app_name("local-example").build()
dag = context.from_pylist(["hello", "world"]).map(func=process)
dag.execute()

for r in dag.stage.results:
    print(r.raw_output)
```

### Example 2: Agent in a Apptainer Container

```python
from agentdist.agentdist import AgentFlowContext
from agentdist.structures.agent import AgentConfig
from agentdist.structures.executor import ContainerExecConfig
import json, os

opencode_cfg = {
    "$schema": "https://opencode.ai/config.json",
    "permission": {"bash": "allow", "edit": "allow", "read": "allow"},
    "provider": {
        "vllm": {
            "npm": "@ai-sdk/openai-compatible",
            "options": {"baseURL": "http://vllm-service/v1"},
            "models": {"my-model": {"name": "my-model"}},
        }
    },
    "model": "vllm/my-model",
}

agent_config = AgentConfig(
    name="opencode-agent",
    agent="opencode",
    backend="apptainer",
    backend_config=ContainerExecConfig(
        name="swe-task-env",
        image="my-registry/sandbox:latest",
        post_setup_commands=["git clone https://github.com/org/repo /workspace"],
        env_vars={"OPENCODE_CONFIG_CONTENT": json.dumps(opencode_cfg)},
    ),
    run_dir="/workspace",
    agent_run_timeout=3600,
)

context = AgentFlowContext.builder.app_name("swe-run").config("concurrent_tasks", 10).build()
dag = (
    context.from_pylist(["Fix the null pointer exception in src/parser.py"])
    .map(func=agent_config, instruction=lambda ctx: ctx.data.metadata["data"])
    .save(target_path="/results/swe-run-001", save_failed=True)
)
dag.execute()
```