from agentdist.structures.agent import AgentContext, AgentResult
from agentdist.executors import ExecutionBackend
from agentdist.executors import ExecutorFactory
from agentdist.agents import AgentFactory
from agentdist.constants import (
    _CONCURRENT_TASKS,
    _UDF_WRAPPER,
    _DEFAULT_PACKAGE_IN_ENV_DIR,
    _PACKAGE_ENV_SETUP,
    _ENV_ENABLE_CMD,
    _JOB_SETUP_SCRIPT,
    METRICS_FIELD_NAME,
    _DYNAMIC_CONCURRENT_WAIT_SEC,
    _DEFAULT_EVENT_BUS_PORT,
)
from pathlib import Path
from agentdist.exceptions import OrchestratorError
from agentdist.structures.executor import ExecConfig
from typing import Dict, List, Any
import asyncio
from agentdist.observability.logging import Logger
from agentdist.orchestrator.dataobject import DataObject
import atexit
from uuid import uuid4
from agentdist.structures.agent import AgentCoreConfig
from agentdist.structures.dataobject import (
    Task,
    TaskResult,
    Stage,
    TaskContext,
    DataObjectTypes,
    StageQueue,
)
import tempfile
import cloudpickle
import os
import shutil
import time
from agentdist.observability.instruments import (
    TASK_EXECUTION_COUNT,
    TASK_EXECUTION_DURATION,
    TASK_ENV_SETUP_DURATION,
    TASK_ARTIFACT_COPY_DURATION,
    TASK_AGENT_RUN_DURATION,
    ACTIVE_TASKS,
    JOB_EXECUTION_DURATION,
    JOB_EXECUTION_COUNT,
    STAGE_EXECUTION_DURATION,
    STAGE_ENV_TEARDOWN_DURATION,
    TASK_SETUP_DURATION,
    OUTPUT_TOKEN_COUNTER as TOKEN_COUNTER,
    NO_OF_INPUT_TASKS,
)
import base64
import inspect
from agentdist.orchestrator.budget import (
    Budget, GroupBudget, LocalBudget
)
from agentdist.events.eventbus import EventBus, Event
from agentdist.events.eventbus_server import  EventBusServer

logger = Logger.get_logger(__name__)


class Orchestrator:
    """This is the orchestrator to run the distributed agent execution on the provided execution backend"""

    def __init__(
        self,
        concurrent_tasks: int = _CONCURRENT_TASKS,
        eager_stage_cleanup:bool=False,
        skip_env_setup:bool=False,
        offload_executor:bool=False,
        dyn_con_limiter=None,
        dyn_con_wait_sec:int=_DYNAMIC_CONCURRENT_WAIT_SEC,
        local_task_budget: int = None,
        task_budget: Budget | None = None,
        event_bus: EventBus | None = None,
        enable_event_bus_server: bool = False,
        event_bus_server_port: int = _DEFAULT_EVENT_BUS_PORT,
        group_budget_enabled: bool = False,
        offload_pod_ttl_seconds: int = 86400,
        offload_executor_strategy: str = "pod"
    ):
        self.concurrent_tasks = concurrent_tasks
        self.concurrent_limiter = asyncio.Semaphore(value=concurrent_tasks)
        self.sessions: Dict[str, Dict[str, ExecutionBackend]] = {}
        self._lock = asyncio.Lock()
        self._stage_lock = asyncio.Lock()
        self.eager_cleanup_environment = eager_stage_cleanup
        self.results_dir = tempfile.mkdtemp()
        atexit.register(shutil.rmtree, self.results_dir, ignore_errors=True)
        self.skip_env_setup = skip_env_setup
        if offload_executor:
            raise OrchestratorError(
                "offload_executor is not supported: this build of agentdist runs every task "
                "in-process against a local execution backend."
            )
        self.offload_executor = offload_executor

        ### Added to include the offload the executor strategy
        self.offload_executor_strategy = offload_executor_strategy
        self.offload_pod_ttl_seconds = offload_pod_ttl_seconds
        self._pending_offload_cleanups: set = set()
        self._killer_tasks: Dict[str, asyncio.Task] = {}


        # Check the dynamic concurrency limiter where need to pass the dynamic concurrency limiter function to decide the dynamically control the concurrency
        self.dyn_con = None
        self._resize_task = None
        self.dyn_con_wait_sec = dyn_con_wait_sec
        try:
            if dyn_con_limiter and callable(dyn_con_limiter):
                _dyn_func = inspect.getfullargspec(dyn_con_limiter)
                if ("concurrent_tasks" not in _dyn_func.args) or len(
                    _dyn_func.args
                ) != 1:
                    logger.warning(
                        "The provided dynamic concurrency limiter function arguments are invalid"
                    )
                else:
                    self.dyn_con = dyn_con_limiter
            elif dyn_con_limiter and not callable(dyn_con_limiter):
                logger.warning(
                    "The dynamic concurrency limiter should be executable function which dynamically adjusts the concurrency limit"
                )
        except Exception as e:
            logger.warning(
                f"There is a error in configuring the dynamic concurrency limiter: {e}"
            )

        # I want to add the event bus may be in future all communication happens through event bus
        # currently used for the task completions/budget edits
        self.enable_event_bus_server = enable_event_bus_server
        self.event_bus_port = event_bus_server_port
        self._event_bus = event_bus if event_bus is not None else EventBus()
        self._event_bus_server = None
        self._group_budget_exhausted = False
        self._event_bus.subscribe("concurrency_adjust", self._on_concurrency_adjust)
        self._event_bus.subscribe("budget_exhausted", self._on_budget_exhausted)
        # this is just a flag used for manipulation by any other tasks
        self.flag_group_batch_enabled = group_budget_enabled
        self.flag_local_task_budget = local_task_budget
        self.flag_task_budget = task_budget

        self._group_budget_exhausted = False
        self._budget = None
        self._setup_budget()
        

    def reinitialize(self):
        """Reinitializes the orchestrator"""
        self.concurrent_limiter = asyncio.Semaphore(value=self.concurrent_tasks)
        self.sessions: Dict[str, Dict[str, ExecutionBackend]] = {}
        self._lock = asyncio.Lock()
        self._stage_lock = asyncio.Lock()
        self.results_dir = tempfile.mkdtemp()
        if (
            (self.dyn_con is not None)
            and (self._resize_task is not None)
            and (not self._resize_task.done())
        ):
            self._resize_task.cancel()
        self._resize_task = None
        for killer_task in self._killer_tasks.values():
            if not killer_task.done():
                killer_task.cancel()
        self._killer_tasks = {}
        self._pending_offload_cleanups = set()
        self._setup_budget()
        atexit.register(shutil.rmtree, self.results_dir, ignore_errors=True)

    def _setup_budget(self):
        """Just reusable method for setting up the budget"""
        if self.flag_local_task_budget is not None:
            self._budget = LocalBudget(self.flag_local_task_budget)
        elif self.flag_task_budget is not None:
            if not isinstance(self.flag_task_budget, Budget):
                logger.warning(
                "The provided task_budget does not implement the Budget protocol so ignoring..."
            )
            else:
                self._budget = self.flag_task_budget
        elif self.flag_group_batch_enabled:
            self._budget = GroupBudget(self)
    def _apply_concurrency(self, next_concurrency: int):
        """Just a resuable method for applying the concurrency"""
        if next_concurrency <= self.concurrent_tasks:
            return
        diff = next_concurrency - self.concurrent_tasks
        logger.debug(
            f"Resizing the concurrency from {self.concurrent_tasks} to {next_concurrency}"
        )
        if diff > 0:
            for _ in range(diff):
                self.concurrent_limiter.release()
            self.concurrent_tasks = next_concurrency

    async def _resize_concurrency(self):
        try:
            while True:
                if not self.dyn_con or not callable(self.dyn_con):
                    break
                await asyncio.sleep(self.dyn_con_wait_sec)
                next_concurrency = self.dyn_con(self.concurrent_tasks)
                self._apply_concurrency(next_concurrency)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Error in dynamic concurrency resize limiter: {e}")

    async def _on_concurrency_adjust(self, event:Event):
        try:
            self._apply_concurrency(int(event.payload["new_concurrent_tasks"]))
        except Exception as e:
            logger.warning(f"Ignoring the concurrency adjust event: {e}")

    async def _on_budget_exhausted(self, event:Event):
        logger.info(
            "Received by the group to mark the group budget as exhausted"
        )
        self._group_budget_exhausted = True

    async def _save_result(self, task_result: TaskResult) -> TaskResult:
        """Saves the full task result to disk and returns a slim result."""
        result_path = os.path.join(self.results_dir, f"{task_result.task_id}.pkl")
        with open(result_path, "wb") as f:
            cloudpickle.dump(task_result, f)

        slim_result = task_result.model_copy(deep=True)
        # Clear large fields to reduce memory
        slim_result.raw_output = None
        slim_result.raw_error = None
        slim_result.parsed_output = None
        slim_result.parsed_error = None
        slim_result.result_path = result_path
        return slim_result

    async def _load_result(self, task_result: TaskResult) -> TaskResult:
        """Loads a full task result from disk if it is a slim result."""
        if task_result.result_path and os.path.exists(task_result.result_path):
            with open(task_result.result_path, "rb") as f:
                return cloudpickle.load(f)
        return task_result

    def cleanup_session(self):
        """The executor which are created to cleanup"""
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=10) as executor:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.set_default_executor(executor)
                loop.run_until_complete(self.cleanup_session_async())
            finally:
                loop.close()

    async def cleanup_session_async(self):
        """The executor which are created to cleanup"""
        await asyncio.gather(
            *[
                asyncio.create_task(executor.stop())
                for executors in self.sessions.values()
                for executor in executors.values()
            ],
            return_exceptions=True,
        )
        if self._pending_offload_cleanups:
            await asyncio.gather(*self._pending_offload_cleanups, return_exceptions=True)
        for killer_task in self._killer_tasks.values():
            if not killer_task.done():
                killer_task.cancel()
        self._killer_tasks = {}
        if self._event_bus_server is not None:
            try:
                await self._event_bus_server.stop()
            except Exception as e:
                logger.debug(f"Failed to stop event bus server: {e}")
            self._event_bus_server = None

    async def cleanup_stage_session(
        self, stage_id: str, executors_to_cleanup: List[str] = None
    ) -> None:
        """The executor which are created to cleanup"""
        executors = self.sessions.get(stage_id, {}).copy()
        if executors_to_cleanup:
            executors = {
                k: executors[k] for k in executors_to_cleanup if k in executors
            }

        env_stop_start = time.time()
        await asyncio.gather(
            *[asyncio.create_task(executor.stop()) for executor in executors.values()],
            return_exceptions=True,
        )
        env_stop_duration = time.time() - env_stop_start

        STAGE_ENV_TEARDOWN_DURATION.record(env_stop_duration, {"stage_id": stage_id})

        if executors and (executors_to_cleanup is None):
            del self.sessions[stage_id]

    def __aenter__(self):
        return self

    def __aexit__(self, exc_type, exc_value, traceback):
        """This is used for the execution of the context manager"""
        self.cleanup_session()

    async def _start_event_bus_server(self):
        """Start backend server thread to post/get the events"""
        if not self.enable_event_bus_server or self._event_bus_server is not None:
            return
        try:
            self._event_bus_server = EventBusServer(
                self._event_bus, port=self.event_bus_port
            )
            await self._event_bus_server.start()
        except Exception as e:
            logger.warning(
                f"Failed to start event bus server on port {self.event_bus_port}: {e}. "
                "But in process event bus will work."
            )
            self._event_bus_server = None

    async def run_job(self, data_object: DataObject):
        await self._start_event_bus_server()
        await self.run_dag(data_object)

    async def run_dag(self, data_object: DataObject):
        """Iterate over the DAG of data objects"""
        start_time = time.time()
        job_status = "success"
        dag_queue = []
        curr = data_object
        stage_queue = []
        # default stage id
        stage_id = uuid4().hex
        _env_cleanup = False
        while curr is not None:
            stage_queue.insert(0, curr)
            if curr.stage:
                stage_id = curr.stage.stage_id
            if curr.isolate:
                _q = StageQueue(
                    stage_id=stage_id,
                    operation=stage_queue,
                    _prev_env_cleanup=_env_cleanup,
                )
                dag_queue.insert(0, _q)
                _env_cleanup = curr.cleanup_prev_stage
                stage_queue = []
            curr = curr.parent
        if stage_queue:
            _q = StageQueue(
                stage_id=stage_id, operation=stage_queue, _prev_env_cleanup=_env_cleanup
            )
            dag_queue.insert(0, _q)

        ### Commented because conversion of the stage to stage group
        # for stage in dag_queue:
        #     _stage_id = uuid1().hex
        #     for do in stage:
        #         if do.is_materialized:
        #             continue
        #         logger.info(f"Executing stage with operation: {do.operation}")
        #         await self.run_stage(do, stage_id=_stage_id)
        #         logger.info(f"Stage {do.operation} completed.")

        try:
            for stage_grp in dag_queue:
                _stage_id = stage_grp.stage_id
                logger.info(f"Stream Execution of the stage with id: {_stage_id}")
                await self.stream_stage(stage_grp)
                logger.info(
                    f"Completed the Stream Execution of the stage with id: {_stage_id}"
                )
        except Exception:
            job_status = "failed"
            raise
        finally:
            duration = time.time() - start_time
            JOB_EXECUTION_DURATION.record(duration, {"status": job_status})
            JOB_EXECUTION_COUNT.add(1, {"status": job_status})

    async def stream_stage(self, stream_grp: StageQueue):
        """This method is used to stream the task of one operation to another operation in single stage"""
        if not stream_grp:
            return
        stage_id = stream_grp.stage_id
        parent = stream_grp.operation[0].parent
        iter_index = 0
        for p in stream_grp.operation:
            if p.type == DataObjectTypes.READ:
                p.is_materialized = True
                parent = p
                iter_index += 1
                continue
            if p.type == DataObjectTypes.STREAM:
                p.stage = Stage(stage_id=stage_id, results=[], failed_tasks=[])
                p.is_materialized = True
                parent = p
                iter_index += 1
                continue
            if not p.is_materialized:
                p.stage = Stage(stage_id=stage_id, results=[], failed_tasks=[])
            elif p.is_materialized:
                parent = p
                iter_index += 1
        if iter_index == len(stream_grp.operation):
            logger.info(
                f"The operation in the stage group {stage_id} already materalized So Skipping the execution."
            )
            return

        parent_results = parent.stage.results if parent and parent.stage else []

        stage_start_time = time.time()

        async def _streamer(
            task_result: TaskResult,
            cleanup_environment=False,
            root_operation=None,
            metrics_attributes={},
        ):
            """This function to be used to stream the task of one operation to another operation in single stage"""
            async with self.concurrent_limiter:
                current_result = task_result
                _executors = set()
                for op in stream_grp.operation[iter_index:]:

                    logger.info(
                        "Executing the operation: %s for source task: %s with status:%i",
                        op.operation,
                        current_result.task_id,
                        current_result.status,
                    )
                    previous_failed = current_result.status != 0
                    if previous_failed:
                        if not op.save_failed:
                            logger.warning(
                                f"Skipping operation {op.operation} for item due to previous failure: {current_result.raw_error}."
                            )
                            break
                    task = Task(
                        stage_id=stage_id,
                        data_object_config=op.config,
                        parent_result=current_result,
                    )
                    start_time = time.time()
                    status_label = "success"
                    try:
                        result = await self.run_task(
                            task,
                            op.isolate,
                            operation_name=op.operation,
                            metrics_attributes=metrics_attributes,
                        )
                        next_current_result = result
                        if isinstance(result, TaskResult):
                            if result.metadata.get("executor_id", None):
                                _executors.add(result.metadata["executor_id"])
                            if result.status == 0:
                                if not previous_failed:
                                    async with self._stage_lock:
                                        op.stage.results.append(result)
                            else:
                                status_label = "failed"
                                if not previous_failed:
                                    async with self._stage_lock:
                                        op.stage.failed_tasks.append(result)
                        else:
                            status_label = "failed"
                            err_result = TaskResult(
                                task_id=task.task_id,
                                status=-1,
                                raw_error=f"Unexpected result type: {type(result)}",
                                metadata={"error": "Invalid result type"},
                            )
                            async with self._stage_lock:
                                op.stage.failed_tasks.append(err_result)
                            next_current_result = err_result

                        if previous_failed:
                            current_result = task.parent_result
                        else:
                            current_result = next_current_result

                    except Exception as e:
                        status_label = "failed"
                        logger.error(
                            f"A task failed with an unhandled exception: {e}",
                            exc_info=True,
                        )
                        err_result = TaskResult(
                            task_id=task.task_id,
                            status=-1,
                            raw_error=str(e),
                            metadata={"error": "Unhandled exception"},
                        )
                        async with self._stage_lock:
                            op.stage.failed_tasks.append(err_result)
                        current_result = err_result
                    finally:
                        duration = time.time() - start_time
                        error_type = "none"
                        if status_label == "failed":
                            error_type = "generic_failure"
                            if current_result and isinstance(
                                current_result, TaskResult
                            ):
                                if current_result.raw_error:
                                    error_msg = str(current_result.raw_error).lower()
                                    if (
                                        "timeout" in error_msg
                                        or "timed out" in error_msg
                                    ):
                                        error_type = "timeout"
                                    else:
                                        error_type = "execution_error"

                        attributes = {
                            "stage_id": stage_id,
                            "operation": op.operation,
                            "status": status_label,
                            "error_type": error_type,
                        }
                        TASK_EXECUTION_COUNT.add(
                            1, {**attributes, **metrics_attributes}
                        )
                        TASK_EXECUTION_DURATION.record(
                            duration, {**attributes, **metrics_attributes}
                        )
                        await asyncio.sleep(0.5)

                # Quick cleanup of the environment just for saving the space
                if self.eager_cleanup_environment or cleanup_environment:
                    try:
                        await self.cleanup_stage_session(
                            stage_id, executors_to_cleanup=list(_executors)
                        )
                    except Exception as e:
                        logger.warning(f"There is a problem in deleting the pod {e}")

                if current_result.status == 0:
                    if self._budget:
                        await self._budget.record(success=True)
                    await self._event_bus.pub(
                        "on_item_success", {"task_id": task_result.task_id,"result": task_result}
                    )
                    if (
                        root_operation
                        and root_operation.config.post_exec_callbacks
                        and "on_item_success"
                        in root_operation.config.post_exec_callbacks
                    ):
                        try:
                            root_operation.config.post_exec_callbacks[
                                "on_item_success"
                            ]("on_item_success", task_result, None)
                        except Exception as e:
                            logger.error(f"Post Exec Callback failed: {e}")
                elif current_result.status != 0:
                    if self._budget:
                        await self._budget.record(success=False)
                    await self._event_bus.pub(
                        "on_item_failure", {"task_id": task_result.task_id,"result": task_result}
                    )
                    if (
                        root_operation
                        and root_operation.config.post_exec_callbacks
                        and "on_item_failure"
                        in root_operation.config.post_exec_callbacks
                    ):
                        try:
                            root_operation.config.post_exec_callbacks[
                                "on_item_failure"
                            ]("on_item_failure", task_result, None)
                        except Exception as e:
                            logger.error(f"Post Exec Callback failed: {e}")

        # added to resize task create to dynamic concurrency limiter
        if (self.dyn_con is not None) and (
            (self._resize_task is None) or self._resize_task.done()
        ):
            self._resize_task = asyncio.create_task(self._resize_concurrency())

        if parent and parent.type == DataObjectTypes.STREAM:
            stream_func = parent.config.func_config.func_code["code"]
            instruction = parent.config.instruction
            iterator = iter(stream_func(**instruction))
            pending_tasks = set()
            stop_flag = "_STOP_ITERATION"
            while True:
                if self._budget and await self._budget.is_exhausted():
                    ### AS I mentioned the budget is at stage level, the idea is at the input level, but let's leave it at stage where the parent type==stream where it
                    ### will be starting stage so we can break like this
                    logger.info(
                        f"Completion budget reached for stage {stage_id} no longer pulling new items from the stream source "
                    )
                    break
                item = next(iterator, stop_flag)
                if item is stop_flag:
                    break
                NO_OF_INPUT_TASKS.add(
                    1,
                    {
                        **{"stage_id": stage_id, "operation": parent.operation},
                        **item.get(METRICS_FIELD_NAME, {}),
                    },
                )
                _metrics_attributes = item.get(METRICS_FIELD_NAME, {})
                if METRICS_FIELD_NAME in item:
                    del item[METRICS_FIELD_NAME]
                if isinstance(item, TaskResult):
                    tr = item
                else:
                    tr = TaskResult.create_metadata_task_result(item)
                task = asyncio.create_task(
                    _streamer(
                        tr,
                        stream_grp.cleanup_environment,
                        root_operation=parent,
                        metrics_attributes=_metrics_attributes,
                    )
                )
                pending_tasks.add(task)
                task.add_done_callback(pending_tasks.discard)
                if len(pending_tasks) >= self.concurrent_tasks:
                    await asyncio.wait(
                        pending_tasks, return_when=asyncio.FIRST_COMPLETED
                    )
            if pending_tasks:
                await asyncio.gather(*pending_tasks, return_exceptions=True)
        elif parent_results:
            loaded_parent_results = await asyncio.gather(
                *[self._load_result(r) for r in parent_results]
            )
            _stages_ops = []
            for result in loaded_parent_results:
                if self._budget and await self._budget.is_exhausted():
                    ### AS I mentioned the budget is at stage level, the idea is at the input level, but let's leave it at stage where the parent type==stream where it
                    ### will be starting stage so we can break like this
                    logger.info(
                        f"Completion budget reached for stage {stage_id} no longer pulling new items from the stream source "
                    )
                    break
                _stages_ops.append(
                    asyncio.create_task(
                        _streamer(result, stream_grp.cleanup_environment)
                    )
                )
            result = await asyncio.gather(*_stages_ops, return_exceptions=True)
        else:
            await _streamer(TaskResult.create_metadata_task_result({"initial": True}))
        if stream_grp.cleanup_environment:
            await self.cleanup_stage_session(stage_id)
        for op in stream_grp.operation:
            op.is_materialized = True
        # added to resize task create to dynamic concurrency limiter
        if (
            (self.dyn_con is not None)
            and (self._resize_task is not None)
            and (not self._resize_task.done())
        ):
            self._resize_task.cancel()
            self._resize_task = None
        stage_duration = time.time() - stage_start_time
        STAGE_EXECUTION_DURATION.record(stage_duration, {"stage_id": stage_id})

    # This is for batch execution but i want to change to streaming so, i want to create a stream group
    async def run_stage(self, data_object: DataObject, stage_id: str):
        """Runs a single stage for the provided data object"""
        if data_object.parent is None:
            data_object.is_materialized = True
            # data_object.stage = Stage(stage_id=stage_id,results=[], failed_tasks=[])
            return

        if not data_object.parent.is_materialized:
            raise OrchestratorError(
                "Parent is not materialized. DAG execution order is incorrect."
            )

        parent_results = (
            data_object.parent.stage.results if data_object.parent.stage.results else []
        )

        tasks_to_run = {}
        if parent_results:
            for parent_task_result in parent_results:
                task = Task(
                    data_object_config=data_object.config,
                    parent_result=parent_task_result,
                )
                tasks_to_run[task.task_id] = asyncio.create_task(
                    self.run_task(
                        task, data_object.isolate, operation_name=data_object.operation
                    )
                )
        else:
            task = Task(data_object_config=data_object.config)
            tasks_to_run[task.task_id] = asyncio.create_task(
                self.run_task(
                    task, data_object.isolate, operation_name=data_object.operation
                )
            )

        await asyncio.gather(*tasks_to_run.values(), return_exceptions=True)

        results = []
        failed_tasks = []
        for task_id, res in tasks_to_run.items():
            try:
                result = res.result()
                if isinstance(result, TaskResult):
                    if result.status == 0:
                        results.append(result)
                    else:
                        failed_tasks.append(result)
                else:
                    failed_tasks.append(
                        TaskResult(
                            task_id=task_id,
                            status=-1,
                            raw_error=f"Unexpected result type: {type(result)}",
                            metadata={"error": "Invalid result type"},
                        )
                    )
            except Exception as e:
                logger.error(
                    f"A task failed with an unhandled exception: {e}", exc_info=True
                )
                failed_tasks.append(
                    TaskResult(
                        task_id=task_id,
                        status=-1,
                        raw_error=str(e),
                        metadata={"error": "Unhandled exception"},
                    )
                )

        data_object.stage = Stage(
            stage_id=stage_id, results=results, failed_tasks=failed_tasks
        )
        data_object.is_materialized=True

    async def run_task(
        self,
        task: Task,
        isolate: bool,
        operation_name: str = "unknown",
        metrics_attributes: Dict[str, Any] = {},
    ) -> TaskResult:
        """This method runs a single task, handling agent execution and result parsing."""
        task_metrics: Dict[str, float] = {"start_time": time.time()}
        _status = "skipped"
        error_type = "none"
        metric_attributes = {
            **{
                "stage_id": task.stage_id,
                "operation": operation_name,
            },
            **metrics_attributes,
        }

        ACTIVE_TASKS.add(1, metric_attributes)

        async def _run_task_internal() -> TaskResult:
            nonlocal _status, error_type
            if task.parent_result and task.parent_result.result_path:
                task.parent_result = await self._load_result(task.parent_result)

            # Moving the concurrency limiter to stage streamer to run full stage group at once
            # async with self.concurrent_limiter:
            _task_step = "Task Initialization"
            executor = None
            task_dir = f"/tasks/{task.task_id}"
            task_context = TaskContext(
                task_dir=task_dir,
                data=task.parent_result,
                task_id=task.task_id,
                stage_id=task.stage_id,
            )
            try:
                logger.info(f"Starting task {task.task_id}...")
                if task.data_object_config.agent_config:
                    agent_config = task.data_object_config.agent_config

                    if callable(agent_config):
                        agent_config = agent_config(task_context)

                    _task_step = "Executor Initialization"
                    if (
                        not isolate
                        and task.parent_result
                        and task.parent_result.metadata.get("executor_id")
                    ):
                        executor = self.sessions.get(task.stage_id, {}).get(
                            task.parent_result.metadata["executor_id"]
                        )
                        if executor is None:
                            logger.warning(
                                f"Executor ID {task.parent_result.metadata.get('executor_id')} not found in active sessions. Creating a new one."
                            )

                    if executor is None:
                        _setup_start = time.time()
                        executor_class = ExecutorFactory.get_executor(
                            agent_config.backend
                        )
                        executor = executor_class(
                            env_config=agent_config.backend_config
                        )
                        try:
                            await asyncio.wait_for(
                                executor.start(),
                                timeout=agent_config.backend_config.env_start_timeout,
                            )
                        except asyncio.TimeoutError:
                            logger.error(
                                f"Timeout while starting executor for task {task.task_id}"
                            )
                            raise EnvironmentError(
                                f"Timeout while starting executor for task {task.task_id}"
                            )
                        except Exception as e:
                            raise e

                        await executor.exec(
                            ["mkdir", "-p", _DEFAULT_PACKAGE_IN_ENV_DIR]
                        )
                        if (not self.skip_env_setup) or (
                            not agent_config.backend_config.skip_remote_env_setup
                        ):
                            await executor.exec([_PACKAGE_ENV_SETUP])
                        else:
                            logger.warning("Skipping the environment setup.")
                        async with self._lock:
                            self.sessions[task.stage_id] = self.sessions.get(
                                task.stage_id, {}
                            )

                            self.sessions[task.stage_id][executor.env_id] = executor
                        task_metrics["env_setup_duration"] = time.time() - _setup_start

                    _task_step = "Agent Initialization"
                    agent_class = AgentFactory.get_agent(agent_config.agent)
                    agent = agent_class(
                        executor,
                        AgentCoreConfig(
                            name=agent_config.name,
                            run_timeout=agent_config.agent_run_timeout,
                            skip_setup=agent_config.skip_setup,
                            agent_run_config=agent_config.agent_run_config,
                            agent_path=agent_config.agent_path,
                        ),
                    )

                    _setup_start = time.time()
                    _task_step = "Agent Setup"
                    await agent.setup()
                    task_metrics["agent_setup_duration"] = time.time() - _setup_start
                    _task_step = "Agent Running"
                    env_vars = {}
                    _setup_start = time.time()
                    result = await executor.exec(["mkdir", "-p", task_dir])
                    if result.return_code != 0:
                        raise EnvironmentError(
                            f"Failed to create task directory '{task_dir}'. Stderr: {result.stderr}"
                        )
                    agent_context = AgentContext(
                        task_dir=task_dir,
                        env_vars=env_vars,
                        run_dir=agent_config.run_dir,
                    )

                    instruction = task.data_object_config.instruction
                    if callable(instruction):
                        instruction = instruction(task_context)

                    # copying the artifacts
                    if task.data_object_config.artifacts:
                        copy_files_start = time.time()
                        artifacts = task.data_object_config.artifacts
                        if callable(artifacts):
                            artifacts = artifacts(task_context)
                        for artifact in artifacts:
                            try:
                                if os.path.basename(artifact[0]) == artifact[0]:
                                    target_path = f"{task_dir}/{artifact[0]}"
                                else:
                                    target_path = artifact[0]
                                await executor.put_file(
                                    artifact[1],
                                    target_path,
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Failed to copy the artifact {artifact[1]} to the task directory {task_dir}. Stderr: {e}"
                                )
                        task_metrics["copying_files_duration"] = (
                            time.time() - copy_files_start
                        )
                    task_metrics["task_setup_duration"] = time.time() - _setup_start
                    _setup_start = time.time()
                    agent_result = await agent.run(instruction, agent_context)
                    task_metrics["actual_task_run_duration"] = (
                        time.time() - _setup_start
                    )
                    if not isinstance(agent_result, AgentResult):
                        result = TaskResult(
                            task_id=task.task_id,
                            status=-1,
                            raw_error="The Result Returned by the agent is not supported, It needs to be subclass of the `AgentResult`.",
                        )
                    else:
                        _task_step = "Agent Result Formatting"

                        result = TaskResult.format_agent_result(
                            task.task_id, agent_result
                        )

                        if task.data_object_config.result_parser:
                            _task_step = "Result Parsing"
                            result.parsed_output = (
                                task.data_object_config.result_parser(result.raw_output)
                            )
                    result.metadata["task_dir"] = f"{executor.env_name}://{task_dir}"
                    if result.status == 0:
                        if agent_result.trajectory:
                            TOKEN_COUNTER.add(
                                int(agent_result.trajectory.full_metrics.output_tokens),
                                {"agent": agent_config.name},
                            )
                        logger.info(f"Task {task.task_id} completed successfully.")
                    else:
                        logger.error(f"Task {task.task_id} failed.")
                    result.metadata["executor_id"] = executor.env_id
                    _status = "success" if result.status == 0 else "failed"
                    if result and isinstance(result, TaskResult):
                        if result.raw_error:
                            error_msg = str(result.raw_error).lower()
                            if "timeout" in error_msg or "timed out" in error_msg:
                                error_type = "timeout"
                            else:
                                error_type = "execution_error"
                    return await self._save_result(result)

                elif task.data_object_config.func_config:
                    _task_step = "UDF Execution Starting"

                    udf_config = task.data_object_config.func_config
                    instruction = task.data_object_config.instruction

                    _task_step = "Executor Initialization"
                    if (
                        not isolate
                        and task.parent_result
                        and task.parent_result.metadata.get("executor_id")
                    ):

                        executor = self.sessions.get(task.stage_id, {}).get(
                            task.parent_result.metadata["executor_id"]
                        )
                        if executor is None:
                            logger.warning(
                                f"Executor ID {task.parent_result.metadata.get('executor_id')} not found in active sessions. Creating a new one."
                            )

                    if executor is None:
                        _setup_start = time.time()
                        runtime_config = udf_config.runtime_config
                        if runtime_config is None:
                            raise EnvironmentError(
                                "UDF requires a runtime_config for isolated execution or a parent executor."
                            )

                        executor_class = ExecutorFactory.get_executor(
                            runtime_config.backend
                        )
                        executor = executor_class(
                            env_config=runtime_config.backend_config
                        )
                        try:
                            await asyncio.wait_for(
                                executor.start(),
                                timeout=runtime_config.backend_config.env_start_timeout,
                            )
                        except asyncio.TimeoutError:
                            logger.error(
                                f"Timeout while starting executor for task {task.task_id}"
                            )
                            raise EnvironmentError(
                                f"Timeout while starting executor for task {task.task_id}"
                            )
                        except Exception as e:
                            raise e
                        await executor.exec(
                            ["mkdir", "-p", _DEFAULT_PACKAGE_IN_ENV_DIR]
                        )
                        if (not self.skip_env_setup) or (
                            not runtime_config.backend_config.skip_remote_env_setup
                        ):
                            await executor.exec([_PACKAGE_ENV_SETUP])
                        else:
                            logger.warning("Skipping the environment setup.")
                        async with self._lock:
                            self.sessions[task.stage_id] = self.sessions.get(
                                task.stage_id, {}
                            )
                            self.sessions[task.stage_id][executor.env_id] = executor
                        task_metrics["env_setup_duration"] = time.time() - _setup_start
                    _setup_start = time.time()
                    _task_step = "UDF Task Directory Creation"
                    await executor.exec(["mkdir", "-p", task_dir])

                    if instruction and callable(instruction):
                        instruction = instruction(task_context)
                    else:
                        instruction = task.parent_result

                    remote_payload = {
                        "func": udf_config.func_code["code"],
                        "instruction": instruction,
                    }

                    _task_step = "UDF Uploading the remote execution artifacts"
                    copy_files_start = time.time()
                    with tempfile.NamedTemporaryFile(
                        mode="wb", delete=False
                    ) as f_input:
                        cloudpickle.dump(remote_payload, f_input)
                        input_path = f_input.name

                    with tempfile.NamedTemporaryFile(
                        mode="w", delete=False
                    ) as f_script:
                        f_script.write(_UDF_WRAPPER)
                        script_path = f_script.name

                    try:
                        await executor.put_file(input_path, f"{task_dir}/input.pkl")
                        await executor.put_file(script_path, f"{task_dir}/udf.py")
                    finally:
                        os.unlink(input_path)
                        os.unlink(script_path)
                    task_metrics["copying_files_duration"] = (
                        time.time() - copy_files_start
                    )
                    task_metrics["task_setup_duration"] = time.time() - _setup_start
                    _task_step = "Executing the UDF task"
                    exec_cmd = [
                        _ENV_ENABLE_CMD,
                        "&&",
                        "python",
                        f"{task_dir}/udf.py",
                        f"{task_dir}/input.pkl",
                        f"{task_dir}/output.pkl",
                    ]
                    _setup_start = time.time()
                    result = await executor.exec(exec_cmd, cwd=task_dir)
                    task_metrics["actual_task_run_duration"] = (
                        time.time() - _setup_start
                    )

                    status = 0
                    _out = None
                    _err = None
                    if result.return_code == 0:
                        with tempfile.NamedTemporaryFile(delete=False) as f_output:
                            output_path = f_output.name
                        try:
                            await executor.get_file(
                                f"{task_dir}/output.pkl", output_path, binary=True
                            )
                            with open(output_path, "rb") as f:
                                output = cloudpickle.load(f)

                            if output["status"] == 0:
                                status = 0
                                _out = output["result"]
                            else:
                                status = -1
                                _err = output["result"]
                            if status != 0:
                                logger.error(f"UDF task failed due to {_err}")
                        finally:
                            os.unlink(output_path)
                    else:
                        status = -1
                        _out = result.stdout
                        _err = result.stderr

                    logger.info(f"UDF task {task.task_id} completed.")
                    result = TaskResult(
                        task_id=task.task_id,
                        status=status,
                        raw_error=_err,
                        raw_output=_out,
                    )
                    result.metadata["executor_id"] = executor.env_id
                    result.metadata["task_dir"] = f"{executor.env_name}://{task_dir}"
                    _status = "success" if result.status == 0 else "failed"
                    if result and isinstance(result, TaskResult):
                        if result.raw_error:
                            error_msg = str(result.raw_error).lower()
                            if "timeout" in error_msg or "timed out" in error_msg:
                                error_type = "timeout"
                            else:
                                error_type = "execution_error"
                    return await self._save_result(result)
                else:
                    raise OrchestratorError("Task has no agent or function config.")

            except Exception as e:
                logger.error(
                    f"Task {task.task_id} failed at step '{_task_step}': {e}",
                    exc_info=True,
                )
                metadata = {
                    "failed_step": _task_step,
                    "executor_id": (
                        executor.env_id
                        if executor and hasattr(executor, "env_id")
                        else None
                    ),
                }
                if executor and hasattr(executor, "env_name"):
                    metadata["task_dir"] = f"{executor.env_name}://{task_dir}"
                _status = "failed"
                return await self._save_result(
                    TaskResult(
                        task_id=task.task_id,
                        status=-1,
                        raw_error=str(e),
                        metadata=metadata,
                    )
                )

        try:
            return await _run_task_internal()
        finally:
            ACTIVE_TASKS.add(-1, metric_attributes)

            task_metrics["end_time"] = time.time()
            task_metrics["total_duration"] = (
                task_metrics["end_time"] - task_metrics["start_time"]
            )
            attributes = {
                **metric_attributes,
                **{"status": _status, "error_type": error_type},
            }

            if "env_setup_duration" in task_metrics:
                TASK_ENV_SETUP_DURATION.record(
                    task_metrics["env_setup_duration"], attributes
                )
            if "copying_files_duration" in task_metrics:
                TASK_ARTIFACT_COPY_DURATION.record(
                    task_metrics["copying_files_duration"], attributes
                )
            if "actual_task_run_duration" in task_metrics:
                TASK_AGENT_RUN_DURATION.record(
                    task_metrics["actual_task_run_duration"], attributes
                )
            if "task_setup_duration" in task_metrics:
                TASK_SETUP_DURATION.record(
                    task_metrics["task_setup_duration"], attributes
                )

