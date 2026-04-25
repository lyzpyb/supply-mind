"""
Pipeline Execution Engine — orchestrates Skills in sequence.

Reads YAML pipeline definitions, executes steps with dependency resolution,
handles HITL checkpoints, and produces aggregated output.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING_HITL = "waiting_hitl"


class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some steps failed


@dataclass
class StepResult:
    """Result of a single pipeline step execution."""
    step_name: str
    skill: str
    status: StepStatus
    start_time: str = ""
    end_time: str = ""
    duration_seconds: float = 0.0
    output: dict | None = None
    error: str | None = None
    hitl_status: str | None = None


@dataclass
class PipelineResult:
    """Result of a full pipeline execution."""
    name: str
    status: PipelineStatus
    completed_steps: int = 0
    total_steps: int = 0
    duration_seconds: float = 0.0
    step_results: list[StepResult] = field(default_factory=list)
    output_summary: dict | None = None
    errors: list[str] = field(default_factory=list)
    report_content: str | None = None

    @property
    def success_rate(self) -> float:
        if self.total_steps == 0:
            return 1.0
        return self.completed_steps / self.total_steps


# ── Skill Registry ──

SKILL_REGISTRY: dict[str, type] = {}


def register_skill(name: str, cls: type):
    """Register a Skill class for use in Pipelines."""
    SKILL_REGISTRY[name] = cls


def _get_skill_instance(skill_name: str):
    """Instantiate a Skill by name."""
    # Try direct class lookup first
    if skill_name in SKILL_REGISTRY:
        return SKILL_REGISTRY[skill_name]()

    # Try importing from known locations
    skill_map = {
        "data-profiler": ("supplymind.skills.common.data_profiler.main", "DataProfiler"),
        "demand-forecast": ("supplymind.skills.demand.forecast.main", "DemandForecast"),
        "demand-anomaly": ("supplymind.skills.demand.anomaly.main", "DemandAnomaly"),
        "inventory-classify": ("supplymind.skills.inventory.classify.main", "InventoryClassify"),
        "inventory-safety-stock": ("supplymind.skills.inventory.safety_stock.main", "InventorySafetyStock"),
        "inventory-reorder": ("supplymind.skills.inventory.reorder.main", "InventoryReorder"),
        "report-generator": ("supplymind.skills.common.report_generator.main", "ReportGenerator"),
    }

    if skill_name not in skill_map:
        raise ValueError(f"Unknown skill: {skill_name}. Registered skills: {list(SKILL_REGISTRY.keys())}")

    module_path, class_name = skill_map[skill_name]
    import importlib
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls()


# ── Pipeline Engine ──

class PipelineEngine:
    """Execute SupplyMind Pipelines from YAML definitions."""

    def __init__(
        self,
        pipeline_path: str,
        data_path: str | None = None,
        output_dir: str | None = None,
    ):
        self.pipeline_path = Path(pipeline_path)
        self.data_path = data_path
        self.output_dir = output_dir or ".supplymind/output"
        self.pipeline_def: dict = {}
        self.context: dict[str, Any] = {}  # Shared context ($variables)
        self.step_results: list[StepResult] = []
        self._sse_listeners: list = []  # For Dashboard SSE

    def run(self) -> PipelineResult:
        """Execute the full pipeline."""
        start_time = time.time()

        # Load pipeline definition
        self.pipeline_def = self._load_pipeline()
        name = self.pipeline_def.get("name", "unnamed")
        steps_def = self.pipeline_def.get("steps", [])
        params = self.pipeline_def.get("params", {})

        total_steps = len(steps_def)

        logger.info(f"Starting pipeline '{name}' with {total_steps} steps")

        # Load initial data into context
        if self.data_path:
            self._load_data_into_context()

        # Store global params
        self.context["$params"] = params

        # Execute each step
        completed = 0
        errors = []
        status = PipelineStatus.RUNNING

        for i, step_def in enumerate(steps_def):
            step_name = step_def.get("skill", f"step_{i}")
            result = self._execute_step(step_def, i)

            self.step_results.append(result)
            self._emit_sse_event("step_completed", {
                "step_index": i,
                "step_name": step_name,
                "status": result.status.value,
                "duration": result.duration_seconds,
            })

            if result.status == StepStatus.COMPLETED:
                completed += 1
                # Store output as $variable
                output_var = step_def.get("output")
                if output_var and result.output:
                    var_name = output_var.lstrip("$")
                    self.context[var_name] = result.output
                    logger.info(f"Stored ${var_name} from step '{step_name}'")

            elif result.status == StepStatus.FAILED:
                on_error = step_def.get("on_error", "abort")
                error_msg = f"Step '{step_name}' failed: {result.error}"
                errors.append(error_msg)
                logger.error(error_msg)

                if on_error == "abort":
                    status = PipelineStatus.FAILED
                    break
                elif on_error == "skip":
                    continue
                elif on_error == "retry":
                    retry_cfg = step_def.get("retry", {"max": 3, "delay": 5})
                    max_retries = retry_cfg.get("max", 3)
                    for attempt in range(max_retries):
                        logger.info(f"Retrying step '{step_name}', attempt {attempt + 1}/{max_retries}")
                        time.sleep(retry_cfg.get("delay", 5))
                        result = self._execute_step(step_def, i)
                        if result.status == StepStatus.COMPLETED:
                            completed += 1
                            break
                    else:
                        status = PipelineStatus.PARTIAL

        duration = time.time() - start_time

        # Determine final status
        if status == PipelineStatus.RUNNING:
            status = (
                PipelineStatus.COMPLETED if completed == total_steps
                else (PipelineStatus.PARTIAL if completed > 0 else PipelineStatus.FAILED)
            )

        # Generate report
        report = self._generate_report(name, status)

        # Build summary
        summary = self._build_summary()

        result = PipelineResult(
            name=name,
            status=status,
            completed_steps=completed,
            total_steps=total_steps,
            duration_seconds=duration,
            step_results=self.step_results,
            output_summary=summary,
            errors=errors,
            report_content=report,
        )

        # Save outputs
        self._save_outputs(result)

        return result

    def _load_pipeline(self) -> dict:
        """Load and parse the pipeline YAML file."""
        with open(self.pipeline_path, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f)

        if not isinstance(content, dict):
            raise ValueError(f"Pipeline file must contain a YAML mapping, got {type(content)}")

        # Validate required fields
        if "steps" not in content:
            raise ValueError("Pipeline must have 'steps' defined")

        return content

    def _load_data_into_context(self):
        """Load input data and store in context."""
        from supplymind.protocol.adapter import load_dataset

        path = self.data_path
        base_dir = os.path.dirname(path) if path else "."

        demand_path = path
        sku_path = None
        inv_path = None

        # Look for companion files
        base_name = os.path.splitext(os.path.basename(path))[0]
        for candidate in [f"{base_name}_sku.csv", f"{base_name}_skus.csv", "sku_master.csv"]:
            cand = os.path.join(base_dir, candidate) if base_dir else candidate
            if os.path.exists(cand):
                sku_path = cand
                break
        for candidate in [f"{base_name}_inventory.csv", "inventory.csv"]:
            cand = os.path.join(base_dir, candidate) if base_dir else candidate
            if os.path.exists(cand):
                inv_path = cand
                break

        data = load_dataset(demand_path=demand_path, sku_path=sku_path, inventory_path=inv_path)
        self.context["$input_data"] = data.model_dump() if hasattr(data, 'model_dump') else data
        self.context["$data_path"] = path
        logger.info(f"Loaded {len(data.demand_history)} demand records from {path}")

    def _execute_step(self, step_def: dict, index: int) -> StepResult:
        """Execute a single pipeline step."""
        step_start = time.time()
        skill_name = step_def.get("skill", f"step_{index}")
        hitl_config = step_def.get("hitl")

        step_result = StepResult(
            step_name=f"step_{index}_{skill_name}",
            skill=skill_name,
            status=StepStatus.RUNNING,
            start_time=datetime.now().isoformat(),
        )

        try:
            # Get skill instance
            skill_instance = _get_skill_instance(skill_name)

            # Prepare input
            input_data = self._prepare_step_input(step_def)

            # Check HITL
            if hitl_config and hitl_config.get("level") != "none":
                step_result.hitl_status = self._handle_hitl(hitl_config, input_data)

            # Run the skill
            output = skill_instance.run(input_data)

            # Convert to dict if it's a Pydantic model
            if hasattr(output, 'model_dump'):
                output_dict = output.model_dump()
            elif isinstance(output, dict):
                output_dict = output
            else:
                output_dict = {"raw_output": str(output)}

            step_result.status = StepStatus.COMPLETED
            step_result.output = output_dict

        except Exception as e:
            step_result.status = StepStatus.FAILED
            step_result.error = f"{type(e).__name__}: {str(e)}"
            logger.error(f"Step '{skill_name}' error: {e}\n{traceback.format_exc()}")

        step_result.end_time = datetime.now().isoformat()
        step_result.duration_seconds = time.time() - step_start

        return step_result

    def _prepare_step_input(self, step_def: dict) -> dict | Any:
        """Prepare input data for a step, resolving $variable references."""
        input_expr = step_def.get("input")
        params = step_def.get("params", {})

        if input_expr is None:
            # Default: pass $profiled or $cleaned or $input_data
            for var in ["$cleaned", "$profiled", "$forecast", "$input_data"]:
                if var.lstrip("$") in self.context:
                    return self.context[var.lstrip("$")]
            return {}

        if isinstance(input_expr, str):
            # Resolve variable reference
            var_name = input_expr.lstrip("$")
            if var_name in self.context:
                data = self.context[var_name]
                # Merge with params
                if isinstance(data, dict):
                    return {**data, **params}
                return data
            return params

        return input_expr

    def _handle_hitl(self, hitl_config: dict, input_data: Any) -> str:
        """Handle HITL checkpoint. In Phase 1, auto-approve non-collaborate levels."""
        level = hitl_config.get("level", "auto")

        if level == "auto":
            return "auto_approved"

        # In Phase 1, we log but auto-approve review/collaborate
        # Full HITL UI integration comes with Dashboard
        logger.info(f"HITL checkpoint at level={level} (auto-approved in CLI mode)")
        return f"auto_approved_cli_{level}"

    def _emit_sse_event(self, event_type: str, data: dict):
        """Emit SSE event for Dashboard listeners."""
        for listener in self._sse_listeners:
            try:
                listener(event_type, data)
            except Exception:
                pass

    def add_sse_listener(self, callback):
        """Register an SSE event listener."""
        self._sse_listeners.append(callback)

    def _generate_report(self, name: str, status: PipelineStatus) -> str:
        """Generate a Markdown report of the pipeline execution."""
        sections = []

        # Summary section
        summary_data = {
            "Pipeline Name": name,
            "Status": status.value,
            "Steps Completed": f"{self.success_rate * 100:.0f}%",
            "Duration": f"{sum(r.duration_seconds for r in self.step_results):.1f}s",
        }
        sections.append({"type": "summary", "title": "Pipeline Execution Summary", "data": summary_data})

        # Per-step results table
        headers = ["Step", "Skill", "Status", "Duration(s)", "Error"]
        rows = []
        for sr in self.step_results:
            rows.append([
                sr.step_name,
                sr.skill,
                sr.status.value,
                f"{sr.duration_seconds:.2f}",
                sr.error[:50] if sr else "",
            ])
        sections.append({"type": "table", "title": "Step Details", "data": {"headers": headers, "rows": rows}})

        # Include key outputs
        for var_name in ["$profiled", "$forecast", "$reorder", "$classify"]:
            if var_name.lstrip("$") in self.context:
                output_data = self.context[var_name.lstrip("$")]
                if isinstance(output_data, dict):
                    # Determine section type from content
                    if "forecasts" in output_data:
                        sections.append({"type": "forecast", "title": "Demand Forecast Results", "data": output_data})
                    elif "suggestions" in output_data:
                        sections.append({"type": "reorder", "title": "Reorder Suggestions", "data": output_data})
                    elif "matrix" in output_data:
                        sections.append({"type": "abcxyz", "title": "ABC-XYZ Classification", "data": output_data})
                    elif "per_sku_summary" in output_data:
                        sections.append({"type": "anomaly", "title": "Anomaly Detection", "data": output_data})
                    else:
                        sections.append({"type": "summary", "title": f"Output: {var_name}", "data": output_data})

        # Generate report using ReportGenerator
        from supplymind.skills.common.report_generator.main import ReportGenerator
        from supplymind.skills.common.report_generator.schema import ReportInput

        generator = ReportGenerator()
        report_input = ReportInput(title=f"SupplyMind — {name} Pipeline Report", sections=sections)
        result = generator.run(report_input)
        return result.content

    def _build_summary(self) -> dict:
        """Build a quick summary dictionary from all outputs."""
        summary = {"pipeline_name": self.pipeline_def.get("name", "unknown")}
        for var_name, value in self.context.items():
            if var_name.startswith("$"):
                continue
            if isinstance(value, dict) and "summary" in value:
                summary.update(value["summary"])
        return summary

    def _save_outputs(self, result: PipelineResult):
        """Save pipeline outputs to files."""
        os.makedirs(self.output_dir, exist_ok=True)

        # Save JSON output
        output_json = {
            "pipeline_name": result.name,
            "status": result.status.value,
            "duration_seconds": round(result.duration_seconds, 2),
            "steps": [
                {
                    "step": sr.step_name,
                    "skill": sr.skill,
                    "status": sr.status.value,
                    "duration": round(sr.duration_seconds, 2),
                    "error": sr.error,
                }
                for sr in self.step_results
            ],
            "summary": result.output_summary,
            "errors": result.errors,
        }

        json_path = os.path.join(self.output_dir, "pipeline_output.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(output_json, f, indent=2, ensure_ascii=False, default=str)

        # Save report
        if result.report_content:
            report_path = os.path.join(self.output_dir, "report.md")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(result.report_content)

            # Also save HTML version
            html_path = os.path.join(self.output_dir, "report.html")
            from supplymind.skills.common.report_generator.main import ReportGenerator
            from supplymind.skills.common.report_generator.schema import ReportInput
            generator = ReportGenerator()

            # Re-extract sections from context
            sections = []
            for var_name, value in self.context.items():
                if var_name.startswith("$"):
                    continue
                if isinstance(value, dict):
                    sections.append({"type": "summary", "title": var_name, "data": value})

            html_input = ReportInput(title=f"SupplyMind — {result.name}", sections=sections, format="html")
            html_result = generator.run(html_input)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_result.content)

        logger.info(f"Outputs saved to {self.output_dir}")
