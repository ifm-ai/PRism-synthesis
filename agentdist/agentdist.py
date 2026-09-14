import asyncio
from typing import List, Any
from uuid import uuid1
from agentdist.orchestrator.orchestrator import Orchestrator
from agentdist.orchestrator.dataobject import DataObject
from agentdist.constants import _CONCURRENT_TASKS, _DYNAMIC_CONCURRENT_WAIT_SEC, _DEFAULT_EVENT_BUS_PORT
from agentdist.structures.dataobject import (
    DataObjectTypes,
    UDFConfig,
    DataObjectConfig,
    Stage,
    TaskResult,
)
from agentdist.observability.logging import Logger
from agentdist.observability.telemetry import configure_telemetry

logger = Logger.get_logger(__name__)


class AgentFlowContext:
    """This is the context to be used by the user to interact with orchestrator"""

    class _Builder:
        def __init__(self):
            self._config = {}

        def app_name(self, app_name: str):
            self._config["app_name"] = app_name
            return self

        def config(self, key, value):
            self._config[key] = value
            return self

        def build(self):
            """This is to build the context where entry point to interact"""
            orc = Orchestrator(
                concurrent_tasks=self._config.get(
                    "concurrent_tasks", _CONCURRENT_TASKS
                ),
                eager_stage_cleanup=self._config.get("eager_stage_cleanup", False),
                skip_env_setup=self._config.get("skip_env_setup", False),
                offload_executor=self._config.get("offload_executor", False),
                dyn_con_limiter=self._config.get("dyn_con_limiter", None),
                dyn_con_wait_sec=self._config.get(
                    "dyn_con_wait_sec", _DYNAMIC_CONCURRENT_WAIT_SEC
                ),
                local_task_budget=self._config.get("local_task_budget", None),
                task_budget=self._config.get("task_budget", None),
                enable_event_bus_server=self._config.get("enable_event_bus_server", False),
                event_bus_server_port=self._config.get(
                    "event_bus_server_port", _DEFAULT_EVENT_BUS_PORT
                ),
                event_bus = self._config.get(
                    "event_bus", None
                ),
                group_budget_enabled=self._config.get("group_budget_enabled", False),
            )

            # Testing the telemetry setup
            telemetry_config = {}
            for key in self._config:
                if key.startswith("telemetry."):
                    telemetry_config[key] = self._config[key]
            configure_telemetry(
                exporter_type=self._config.get("telemetry.exporter_type", "console"),
                endpoint=self._config.get("telemetry.exporter_endpoint"),
                metrics_file=self._config.get("telemetry.metrics_file"),
                export_interval_millis=self._config.get(
                    "telemetry.export_interval_millis", 60000
                ),
                resource_attributes=self._config.get("telemetry.resource_attributes"),
            )
            return AgentFlowContext(
                app_name=self._config.get("app_name", f"app-{uuid1().hex}"),
                orchestrator=orc,
                telemetry_config=telemetry_config,
            )

    builder = _Builder()

    def __init__(
        self,
        app_name: str,
        orchestrator: "Orchestrator",
        telemetry_config: dict = None,
    ):
        self.app_name = app_name
        self._orc = orchestrator
        self.telemetry_config = telemetry_config

    def reinitialize(self):
        """Reinitializes the context if executing in worker mode"""
        self._orc.reinitialize()
        configure_telemetry(
            exporter_type=self.telemetry_config.get(
                "telemetry.exporter_type", "console"
            ),
            endpoint=self.telemetry_config.get("telemetry.exporter_endpoint"),
            metrics_file=self.telemetry_config.get("telemetry.metrics_file"),
            export_interval_millis=self.telemetry_config.get(
                "telemetry.export_interval_millis", 60000
            ),
            resource_attributes=self.telemetry_config.get(
                "telemetry.resource_attributes"
            ),
        )

    def from_pylist(self, data: List[Any]):
        return DataObject(
            parent=None,
            type=DataObjectTypes.READ,
            operation="pyread",
            config=None,
            context=self,
            stage=Stage(
                stage_id=uuid1().hex,
                results=[TaskResult.create_metadata_task_result(i) for i in data],
            ),
        )

    def from_stream(self, func: UDFConfig):
        """This function used to stream data from the streamer"""

        return DataObject(
            parent=None,
            type=DataObjectTypes.STREAM,
            operation="stream",
            config=DataObjectConfig(
                func_config=func,
            ),
            context=self,
        )

    def execute(self, data_object: DataObject):
        """The dag execution entry point"""
        self._execute_local(data_object)

    def _execute_local(self, data_object: DataObject):
        """Executes the dag locally"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._orc.run_job(data_object))
        finally:
            loop.run_until_complete(self._orc.cleanup_session_async())


