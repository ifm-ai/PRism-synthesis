from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    PeriodicExportingMetricReader,
    ConsoleMetricExporter,
    MetricExporter,
    MetricExportResult,
)
from typing import Callable, Any
from opentelemetry.sdk.resources import Resource
from typing import Optional
import json
import os


class ReadableConsoleMetricExporter(MetricExporter):
    """
    A custom OpenTelemetry exporter that prints a readable summary of tasks and stages
    to the console and optionally writes to a file.
    """

    def __init__(
        self,
        output_file: Optional[str] = None,
    ):
        super().__init__()
        self.output_file = output_file

    def export(
        self,
        metrics_data,
        timeout_millis: float = 10_000,
        **kwargs,
    ) -> MetricExportResult:
        # Data structures for aggregation `This is LLM Generated`
        summary = {
            "active_tasks": 0,
            "total_tokens": 0,
            "no_of_input_tasks": 0,
            "task_execution": {"success": 0, "failed": 0, "total": 0},
            "stages": {},
        }
        details = []

        # Aggregate metrics from the OTel data model
        for resource_metric in metrics_data.resource_metrics:
            for scope_metric in resource_metric.scope_metrics:
                for metric in scope_metric.metrics:
                    # Prepare detailed metric entry
                    metric_detail = {
                        "name": metric.name,
                        "description": metric.description,
                        "unit": metric.unit,
                        "data": [],
                    }

                    for point in metric.data.data_points:
                        attributes = dict(point.attributes) if point.attributes else {}
                        point_data = {
                            "attributes": attributes,
                            "time_unix_nano": point.time_unix_nano,
                        }

                        # Handle value types
                        if hasattr(point, "value"):
                            point_data["value"] = point.value
                        elif hasattr(point, "count"):  # Histogram
                            point_data["count"] = point.count
                            point_data["sum"] = point.sum
                            if hasattr(point, "min"):
                                point_data["min"] = point.min
                            if hasattr(point, "max"):
                                point_data["max"] = point.max

                        metric_detail["data"].append(point_data)

                        # --- Summary Aggregation Logic ---
                        stage_id = attributes.get("stage_id", "unknown")

                        # Ensure stage entry exists
                        if stage_id not in summary["stages"]:
                            summary["stages"][stage_id] = {
                                "active": 0,
                                "success": 0,
                                "failed": 0,
                                "total": 0,
                            }
                        if metric.name == "agent.llm.output_tokens":
                            val = point.value
                            summary["total_tokens"] += val
                        if metric.name == "agentdist.orchestrator.active_tasks":
                            val = point.value
                            summary["active_tasks"] += val
                            summary["stages"][stage_id]["active"] += val

                        elif metric.name == "agentdist.task.execution_count":
                            status = attributes.get("status", "unknown")
                            count = point.value

                            summary["task_execution"]["total"] += count
                            summary["stages"][stage_id]["total"] += count

                            if status == "success":
                                summary["task_execution"]["success"] += count
                                summary["stages"][stage_id]["success"] += count
                            elif status == "failed":
                                summary["task_execution"]["failed"] += count
                                summary["stages"][stage_id]["failed"] += count
                        elif metric.name == "agentdist.job.no_of_input_tasks":
                            summary["no_of_input_tasks"] += point.value

                    details.append(metric_detail)

        # Construct the full report
        full_report = {"summary": summary, "details": details}

        # Write to file if configured
        if self.output_file or os.environ.get("AGENTDIST_METRICS_FILE"):
            try:
                target_file = self.output_file if self.output_file else os.environ.get("AGENTDIST_METRICS_FILE")
                with open(target_file, "w") as f:
                    json.dump(full_report, f, indent=2)
            except Exception as e:
                print(f"Error writing metrics to file: {e}")
        # Print readable summary to console
        self._print_console_summary(summary)

        return MetricExportResult.SUCCESS

    def _print_console_summary(self, summary):
        lines = ["===== Orchestrator Status ====="]
        lines.append(f"Total Active Tasks: {summary['active_tasks']}")
        lines.append(f"Total Output Tokens: {summary['total_tokens']}")
        lines.append(f"No. of Input Tasks: {summary['no_of_input_tasks']}")
        lines.append(
            f"Total Completed: {summary['task_execution']['total']} (Success: {summary['task_execution']['success']}, Failed: {summary['task_execution']['failed']})"
        )

        if summary["stages"]:
            lines.append("\nStages:")
            for stage_id, stats in summary["stages"].items():
                if (
                    stage_id == "unknown"
                    and stats["total"] == 0
                    and stats["active"] == 0
                ):
                    continue
                status_str = "RUNNING" if stats["active"] > 0 else "IDLE"
                lines.append(f"  Stage: {stage_id} [{status_str}]")
                lines.append(
                    f"    Active: {stats['active']}, Success: {stats['success']}, Failed: {stats['failed']}"
                )

        lines.append("=" * 30)
        print("\n".join(lines))

    def shutdown(self, timeout_millis: float = 30_000, **kwargs) -> None:
        pass

    def force_flush(self, timeout_millis: float = 30_000) -> bool:
        return True


def configure_telemetry(
    exporter_type: str = "console",
    endpoint: str = None,
    service_name: str = "agentdist",
    metrics_file: str = None,
    export_interval_millis: int = 60000,
    resource_attributes: dict = None,
):
    """
    Configures the OpenTelemetry MeterProvider.

    Args:
        exporter_type: 'console' for local debugging, 'otlp' for remote backends (Prometheus, Datadog, etc.)
        endpoint: The OTLP endpoint URL (required if exporter_type is 'otlp')
        service_name: The name of the service for the resource.
        metrics_file: Path to a file where metrics summary should be written.
        export_interval_millis: How often to update the metrics (default 5s).
        resource_attributes: Additional attributes to identify the resource (e.g. job_id, task_id).
    """
    attributes = {"service.name": service_name}
    if resource_attributes:
        attributes.update(resource_attributes)

    resource = Resource.create(attributes=attributes)
    metrics_readers = []
    exporter_type = exporter_type.lower().split(",")
    if "otlp" in exporter_type:
        # Requires: pip install opentelemetry-exporter-otlp
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )

        exporter = OTLPMetricExporter(endpoint=endpoint) if endpoint else OTLPMetricExporter()
        reader = PeriodicExportingMetricReader(
        exporter, export_interval_millis=export_interval_millis
    )
        metrics_readers.append(reader)
    if ("console" in exporter_type) or (not metrics_readers):
        # Use our custom readable exporter instead of the default JSON one
        exporter = ReadableConsoleMetricExporter(
            output_file=metrics_file
        )
        reader = PeriodicExportingMetricReader(
        exporter, export_interval_millis=export_interval_millis
    )   
        metrics_readers.append(reader)

    
    provider = MeterProvider(metric_readers=metrics_readers, resource=resource)
    metrics.set_meter_provider(provider)
