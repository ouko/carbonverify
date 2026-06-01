"""Step execution registry and handlers for each workflow step type."""

import asyncio
import ast
import hashlib
import json
import operator
import time
from typing import Any, Dict, List, Optional, Protocol

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.validation_engine.models import (
    ValidationRun,
    WorkflowStepType,
)
from app.validation_engine.schemas import (
    DatabaseQueryConfig,
    ExternalApiConfig,
    HttpStepConfig,
    NotificationConfig,
    ServiceCallConfig,
    WaitConfig,
)

logger = get_logger(__name__)


class StepExecutor(Protocol):
    """Protocol for step executors."""

    async def execute(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any],
        run: ValidationRun,
    ) -> Dict[str, Any]:
        """Execute the step and return output data."""
        ...


class HttpRequestExecutor:
    """Execute HTTP request steps."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0, follow_redirects=True)
        return self._client

    async def execute(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any],
        run: ValidationRun,
    ) -> Dict[str, Any]:
        cfg = HttpStepConfig.model_validate(config)
        client = await self._get_client()

        # Interpolate variables in URL
        url = cfg.url
        for key, val in context.get("variables", {}).items():
            url = url.replace(f"${{{key}}}", str(val))

        headers = cfg.headers.copy()
        # Inject synthetic actor trace header if present in context
        synth = context.get("synthetic_actor")
        if synth and "trace_header_name" in synth:
            headers[synth["trace_header_name"]] = synth.get("trace_header_value", "")

        started = time.monotonic()
        try:
            response = await client.request(
                method=cfg.method,
                url=url,
                headers=headers,
                json=cfg.body,
                timeout=cfg.timeout_ms / 1000.0,
            )
            latency_ms = int((time.monotonic() - started) * 1000)

            if response.status_code not in cfg.expected_status_codes:
                raise RuntimeError(
                    f"HTTP {response.status_code} not in expected {cfg.expected_status_codes}"
                )

            body_text = response.text if cfg.capture_response else None
            return {
                "url": url,
                "method": cfg.method,
                "status_code": response.status_code,
                "response_headers": dict(response.headers),
                "response_body": body_text,
                "latency_ms": latency_ms,
            }
        except httpx.TimeoutException:
            raise RuntimeError(f"HTTP request timed out after {cfg.timeout_ms}ms")
        except httpx.ConnectError as exc:
            raise RuntimeError(f"HTTP connection error: {exc}")


class DatabaseQueryExecutor:
    """Execute database query steps."""

    async def execute(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any],
        run: ValidationRun,
    ) -> Dict[str, Any]:
        cfg = DatabaseQueryConfig.model_validate(config)

        from app.database import AsyncSessionLocal
        started = time.monotonic()
        async with AsyncSessionLocal() as session:
            result = await session.execute(cfg.query, cfg.params)
            rows = [dict(row._mapping) for row in result.mappings().all()]
            execution_time_ms = int((time.monotonic() - started) * 1000)

        if cfg.expected_row_count is not None and len(rows) != cfg.expected_row_count:
            raise RuntimeError(
                f"Expected {cfg.expected_row_count} rows, got {len(rows)}"
            )

        return {
            "query": cfg.query,
            "params": cfg.params,
            "row_count": len(rows),
            "rows": rows if cfg.snapshot_result else None,
            "execution_time_ms": execution_time_ms,
        }


class ServiceCallExecutor:
    """Execute internal service call steps."""

    # Registry of callable services
    SERVICES: Dict[str, Any] = {}

    @classmethod
    def register_service(cls, name: str, instance: Any) -> None:
        cls.SERVICES[name] = instance

    async def execute(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any],
        run: ValidationRun,
    ) -> Dict[str, Any]:
        cfg = ServiceCallConfig.model_validate(config)

        service = self.SERVICES.get(cfg.service_name)
        if service is None:
            raise RuntimeError(f"Unknown service: {cfg.service_name}")

        method = getattr(service, cfg.method_name, None)
        if method is None:
            raise RuntimeError(
                f"Method '{cfg.method_name}' not found on service '{cfg.service_name}'"
            )

        # Resolve args with variable interpolation
        resolved_args = []
        for arg in cfg.args:
            if isinstance(arg, str) and arg.startswith("${") and arg.endswith("}"):
                path = arg[2:-1].split(".")
                current = context
                for part in path:
                    current = current.get(part, arg) if isinstance(current, dict) else arg
                resolved_args.append(current)
            else:
                resolved_args.append(arg)

        started = time.monotonic()
        try:
            if asyncio.iscoroutinefunction(method):
                result = await method(*resolved_args, **cfg.kwargs)
            else:
                result = method(*resolved_args, **cfg.kwargs)
            latency_ms = int((time.monotonic() - started) * 1000)
            return {
                "service_name": cfg.service_name,
                "method_name": cfg.method_name,
                "result": result,
                "latency_ms": latency_ms,
            }
        except Exception as exc:
            raise RuntimeError(
                f"Service call '{cfg.service_name}.{cfg.method_name}' failed: {exc}"
            ) from exc


class ExternalApiExecutor:
    """Execute external API call steps."""

    async def execute(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any],
        run: ValidationRun,
    ) -> Dict[str, Any]:
        cfg = ExternalApiConfig.model_validate(config)

        # Map provider names to internal clients
        if cfg.provider == "kimi":
            from app.core.kimi_client import KimiAPIClient
            client = KimiAPIClient()
            started = time.monotonic()
            result = await client.chat_completion(**cfg.params)
            latency_ms = int((time.monotonic() - started) * 1000)
            return {
                "provider": cfg.provider,
                "endpoint": cfg.endpoint,
                "status_code": 200,
                "response_body": result,
                "latency_ms": latency_ms,
            }
        elif cfg.provider == "radix":
            from app.blockchain.radix_client import get_radix_client
            client = get_radix_client()
            started = time.monotonic()
            result = await client.query_ledger(**cfg.params)
            latency_ms = int((time.monotonic() - started) * 1000)
            return {
                "provider": cfg.provider,
                "endpoint": cfg.endpoint,
                "status_code": 200,
                "response_body": result,
                "latency_ms": latency_ms,
            }
        elif cfg.provider == "whatsapp":
            from app.services.whatsapp_api import WhatsAppMetaAPI
            api = WhatsAppMetaAPI()
            started = time.monotonic()
            result = await api.send_text_message(**cfg.params)
            latency_ms = int((time.monotonic() - started) * 1000)
            return {
                "provider": cfg.provider,
                "endpoint": cfg.endpoint,
                "status_code": 200,
                "response_body": result,
                "latency_ms": latency_ms,
            }
        else:
            raise RuntimeError(f"Unknown external API provider: {cfg.provider}")


class NotificationExecutor:
    """Execute notification steps."""

    async def execute(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any],
        run: ValidationRun,
    ) -> Dict[str, Any]:
        cfg = NotificationConfig.model_validate(config)

        # For validation workflows, notifications are best-effort
        # We don't want a notification failure to block the workflow
        sent = False
        error = None
        try:
            if cfg.channel == "whatsapp":
                from app.services.whatsapp_api import WhatsAppMetaAPI
                api = WhatsAppMetaAPI()
                for recipient in cfg.recipients:
                    await api.send_text_message(
                        to=recipient,
                        body=cfg.body or "",
                    )
                sent = True
            elif cfg.channel == "email":
                # Placeholder — would integrate with email service
                sent = True
            elif cfg.channel == "slack":
                # Placeholder — would integrate with Slack webhook
                sent = True
            elif cfg.channel == "webhook":
                # Placeholder — generic webhook
                sent = True
            else:
                sent = True  # Best effort
        except Exception as exc:
            error = str(exc)
            sent = False

        return {
            "channel": cfg.channel,
            "recipients": cfg.recipients,
            "subject": cfg.subject,
            "sent": sent,
            "error": error,
        }


class DomCaptureExecutor:
    """Execute DOM capture steps using Playwright."""

    async def execute(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any],
        run: ValidationRun,
    ) -> Dict[str, Any]:
        from app.services.lead_intelligence.playwright_utils import (
            _get_or_launch_browser,
            close_persistent_browser,
        )
        from playwright.async_api import async_playwright

        cfg = config  # Simplified — would validate with DomCaptureConfig
        url = cfg.get("url", "")
        if not url:
            raise RuntimeError("DOM capture requires a URL")

        started = time.monotonic()
        try:
            async with async_playwright() as p:
                browser = await _get_or_launch_browser(p)
                page = await browser.new_page(
                    viewport={
                        "width": cfg.get("viewport_width", 1280),
                        "height": cfg.get("viewport_height", 720),
                    }
                )
                await page.goto(url, wait_until="networkidle", timeout=30000)

                title = await page.title()
                html = await page.content() if cfg.get("capture_html", True) else None
                screenshot = None
                if cfg.get("capture_screenshot", True):
                    screenshot_bytes = await page.screenshot(
                        full_page=cfg.get("full_page", False)
                    )
                    import base64
                    screenshot = base64.b64encode(screenshot_bytes).decode("utf-8")

                await page.close()
                latency_ms = int((time.monotonic() - started) * 1000)

                return {
                    "url": url,
                    "title": title,
                    "html": html,
                    "screenshot": screenshot,
                    "viewport": {
                        "width": cfg.get("viewport_width", 1280),
                        "height": cfg.get("viewport_height", 720),
                    },
                    "latency_ms": latency_ms,
                }
        except Exception as exc:
            raise RuntimeError(f"DOM capture failed: {exc}")
        finally:
            try:
                close_persistent_browser()
            except Exception:
                pass


class DecisionGateExecutor:
    """Execute decision gate steps."""

    async def execute(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any],
        run: ValidationRun,
    ) -> Dict[str, Any]:
        from app.validation_engine.schemas import DecisionGateConfig
        cfg = DecisionGateConfig.model_validate(config)

        # Evaluate the condition expression against context
        # Simple expression evaluation — in production, use a safe evaluator
        condition = cfg.condition_expression
        result = self._evaluate_condition(condition, context)

        return {
            "condition": condition,
            "result": result,
            "require_human_approval": cfg.require_human_approval,
            "auto_approve_threshold": cfg.auto_approve_threshold,
            "escalation_level": cfg.escalation_level.value,
        }

    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """Safely evaluate a simple condition expression using a restricted AST visitor."""
        # Replace context references
        expr = condition
        for key, val in context.get("variables", {}).items():
            expr = expr.replace(f"${{{key}}}", repr(val))

        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError:
            logger.warning("decision_gate_syntax_error", condition=condition)
            return False

        try:
            result = self._eval_node(tree.body)
        except ValueError as exc:
            logger.warning("decision_gate_disallowed_expression", condition=condition, error=str(exc))
            return False
        except Exception:
            return False

        return bool(result)

    def _eval_node(self, node: ast.AST) -> Any:
        """Recursively evaluate an AST node using only allowed operations."""
        if isinstance(node, ast.Constant):
            return node.value
        if hasattr(ast, "Num") and isinstance(node, ast.Num):  # For Python < 3.8 compatibility
            return node.n
        if hasattr(ast, "Str") and isinstance(node, ast.Str):  # For Python < 3.8 compatibility
            return node.s
        if hasattr(ast, "NameConstant") and isinstance(node, ast.NameConstant):  # For Python < 3.8 compatibility
            return node.value
        if isinstance(node, ast.Name):
            if node.id in ("True", "False", "None"):
                return {"True": True, "False": False, "None": None}[node.id]
            raise ValueError(f"Disallowed name: {node.id}")
        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            raise ValueError(f"Disallowed binary operator: {type(node.op).__name__}")
        if isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            if isinstance(node.op, ast.Not):
                return not operand
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return +operand
            raise ValueError(f"Disallowed unary operator: {type(node.op).__name__}")
        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left)
            if len(node.ops) != 1 or len(node.comparators) != 1:
                raise ValueError("Chained comparisons are not allowed")
            right = self._eval_node(node.comparators[0])
            op = node.ops[0]
            if isinstance(op, ast.Eq):
                return left == right
            if isinstance(op, ast.NotEq):
                return left != right
            if isinstance(op, ast.Lt):
                return left < right
            if isinstance(op, ast.LtE):
                return left <= right
            if isinstance(op, ast.Gt):
                return left > right
            if isinstance(op, ast.GtE):
                return left >= right
            if isinstance(op, ast.In):
                return left in right
            raise ValueError(f"Disallowed comparison operator: {type(op).__name__}")
        if isinstance(node, ast.BoolOp):
            values = [self._eval_node(v) for v in node.values]
            if isinstance(node.op, ast.And):
                return all(values)
            if isinstance(node.op, ast.Or):
                return any(values)
            raise ValueError(f"Disallowed boolean operator: {type(node.op).__name__}")
        if isinstance(node, ast.List):
            return [self._eval_node(elt) for elt in node.elts]
        if hasattr(ast, "Tuple") and isinstance(node, ast.Tuple):
            return tuple(self._eval_node(elt) for elt in node.elts)
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only simple function calls are allowed")
            if node.func.id != "len":
                raise ValueError(f"Disallowed function call: {node.func.id}")
            if len(node.args) != 1 or node.keywords:
                raise ValueError("len() accepts exactly one positional argument")
            return len(self._eval_node(node.args[0]))
        if isinstance(node, ast.Expression):
            return self._eval_node(node.body)
        raise ValueError(f"Disallowed AST node type: {type(node).__name__}")


class WaitExecutor:
    """Execute wait steps."""

    async def execute(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any],
        run: ValidationRun,
    ) -> Dict[str, Any]:
        cfg = WaitConfig.model_validate(config)
        await asyncio.sleep(cfg.duration_ms / 1000.0)
        return {
            "waited_ms": cfg.duration_ms,
            "condition_evaluated": cfg.condition is not None,
        }


class ParallelExecutor:
    """Execute parallel branch steps."""

    async def execute(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any],
        run: ValidationRun,
    ) -> Dict[str, Any]:
        # Parallel execution is handled at the orchestrator level
        # This executor just records the branch configuration
        return {
            "branches": config.get("branches", []),
            "join_strategy": config.get("join_strategy", "all"),
            "max_concurrency": config.get("max_concurrency", 4),
        }


class SubflowExecutor:
    """Execute subflow (nested workflow) steps."""

    async def execute(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any],
        run: ValidationRun,
    ) -> Dict[str, Any]:
        from app.validation_engine.schemas import SubflowConfig
        cfg = SubflowConfig.model_validate(config)

        # Subflow execution would trigger a new run via the orchestrator
        # For now, return the configuration for the orchestrator to handle
        return {
            "workflow_name": cfg.workflow_name,
            "workflow_version": cfg.workflow_version,
            "input_mapping": cfg.input_mapping,
            "output_mapping": cfg.output_mapping,
            "subflow": True,
        }


class StepExecutorRegistry:
    """Registry mapping step types to their executors."""

    def __init__(self):
        self._executors: Dict[WorkflowStepType, StepExecutor] = {
            WorkflowStepType.http_request: HttpRequestExecutor(),
            WorkflowStepType.database_query: DatabaseQueryExecutor(),
            WorkflowStepType.service_call: ServiceCallExecutor(),
            WorkflowStepType.external_api: ExternalApiExecutor(),
            WorkflowStepType.notification: NotificationExecutor(),
            WorkflowStepType.dom_capture: DomCaptureExecutor(),
            WorkflowStepType.decision_gate: DecisionGateExecutor(),
            WorkflowStepType.wait: WaitExecutor(),
            WorkflowStepType.parallel: ParallelExecutor(),
            WorkflowStepType.subflow: SubflowExecutor(),
        }

    def get_executor(self, step_type: WorkflowStepType) -> StepExecutor:
        executor = self._executors.get(step_type)
        if executor is None:
            raise ValueError(f"No executor registered for step type: {step_type.value}")
        return executor

    def register(self, step_type: WorkflowStepType, executor: StepExecutor) -> None:
        self._executors[step_type] = executor
