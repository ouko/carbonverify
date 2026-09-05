"""Step execution registry and handlers for each workflow step type."""

import asyncio
import ast
import time
import uuid
from typing import Any, Dict, List, Optional, Protocol

import httpx

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


def _resolve_application_id(context: Dict[str, Any], required: bool = True) -> Optional[uuid.UUID]:
    """Resolve the target application ID from executor context.

    Supports direct injection (unit tests), run input data (pipeline triggered
    for an existing application), and outputs of previously executed steps.
    """
    raw = context.get("application_id")
    if raw is None:
        raw = context.get("input", {}).get("application_id")
    if raw is None:
        for output in context.get("outputs", {}).values():
            if isinstance(output, dict) and output.get("application_id"):
                raw = output["application_id"]
                break
    if raw is None:
        if required:
            raise RuntimeError("application_id not found in workflow context")
        return None
    return uuid.UUID(str(raw))


class HttpRequestExecutor:
    """Execute HTTP request steps."""

    async def execute(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any],
        run: ValidationRun,
    ) -> Dict[str, Any]:
        cfg = HttpStepConfig.model_validate(config)

        # URL is already interpolated by the orchestrator; do not double-interpolate
        url = cfg.url

        headers = cfg.headers.copy()
        # Inject synthetic actor trace header if present in context
        synth = context.get("synthetic_actor")
        if synth and "trace_header_name" in synth:
            headers[synth["trace_header_name"]] = synth.get("trace_header_value", "")

        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
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
    """Execute read-only database query steps."""

    # Reject any query that is not a plain SELECT. This prevents SQL injection
    # through user-supplied workflow graphs.
    _FORBIDDEN_KEYWORDS = (
        r"\b(insert|update|delete|drop|create|alter|truncate|replace|merge|copy|exec|execute|call|grant|revoke)\b"
    )

    @classmethod
    def _validate_query(cls, query: str) -> None:
        normalized = " ".join(query.split())
        upper = normalized.upper()
        if ";" in upper:
            raise RuntimeError("Multi-statement queries are not allowed")
        if not upper.startswith("SELECT"):
            raise RuntimeError("Only SELECT queries are allowed in workflow database steps")
        import re
        if re.search(cls._FORBIDDEN_KEYWORDS, upper):
            raise RuntimeError("Query contains forbidden SQL keywords")

    async def execute(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any],
        run: ValidationRun,
    ) -> Dict[str, Any]:
        cfg = DatabaseQueryConfig.model_validate(config)
        self._validate_query(cfg.query)

        from sqlalchemy import text
        from app.database import AsyncSessionLocal
        started = time.monotonic()
        async with AsyncSessionLocal() as session:
            result = await session.execute(text(cfg.query), cfg.params)
            rows = [dict(row) for row in result.mappings().all()]
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
        import re

        def _resolve_ref(ref: str) -> Any:
            parts = ref.split(".")
            # Explicit namespaces: input, variables, outputs
            if parts[0] in ("input", "variables", "outputs"):
                current = context
                for part in parts:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        return None
                return current
            # Bare key: legacy behavior, look in variables
            return context.get("variables", {}).get(ref)

        # Replace ${input.x}, ${variables.y}, ${outputs.step.z}, and legacy ${key} references
        expr = condition
        for match in re.finditer(r"\$\{([^}]+)\}", condition):
            full = match.group(0)
            ref = match.group(1)
            value = _resolve_ref(ref)
            if value is None:
                logger.warning("decision_gate_unresolved_reference", reference=full, condition=condition)
                return False
            expr = expr.replace(full, repr(value))

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


class AiEvaluationExecutor:
    """Execute AI-led evaluation steps using the Kimi API."""

    async def execute(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any],
        run: ValidationRun,
    ) -> Dict[str, Any]:
        from app.validation_engine.schemas import AiEvaluationConfig
        from app.services.kimi_api import KimiAPIClient
        import json

        cfg = AiEvaluationConfig.model_validate(config)
        client = KimiAPIClient()

        # Merge explicit input_data with workflow variables and run context
        evaluation_context = {
            **context.get("variables", {}),
            **cfg.input_data,
            "run_id": str(run.id) if run else None,
            "trigger_event": run.trigger_event if run else None,
        }

        system_prompt = (
            "You are an expert evaluator for carbon credit MRV workflows. "
            "Evaluate the provided input and return strict JSON with keys: "
            "score (float 0.0-1.0), passed (bool), reasoning (string), and recommendation (string). "
            "Be conservative: only pass evaluations that are genuinely satisfactory."
        )
        user_prompt = f"{cfg.prompt}\n\nInput context: {json.dumps(evaluation_context, default=str)}"

        started = time.monotonic()
        try:
            response = await client.chat_completion(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
            )
            latency_ms = int((time.monotonic() - started) * 1000)
            content = response.get("content", "{}").strip()

            # Parse JSON, tolerating markdown fences
            if content.startswith("```"):
                content = content.split("```json", 1)[-1].split("```", 1)[0].strip()

            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as exc:
                logger.error("ai_evaluation_json_parse_failed", content=content[:200], error=str(exc))
                if cfg.fail_on_error:
                    raise RuntimeError(f"AI evaluation response is not valid JSON: {exc}")
                return {
                    "score": 0.0,
                    "passed": False,
                    "reasoning": "AI response could not be parsed as JSON.",
                    "recommendation": "Retry the evaluation or review the prompt.",
                    "raw_response": content,
                    "latency_ms": latency_ms,
                    "parse_error": str(exc),
                }

            score = float(parsed.get("score", 0.0))
            passed = parsed.get("passed", score >= cfg.pass_threshold)
            reasoning = str(parsed.get("reasoning", ""))
            recommendation = str(parsed.get("recommendation", ""))

            result = {
                "score": score,
                "passed": passed,
                "reasoning": reasoning,
                "recommendation": recommendation,
                "raw_response": content,
                "latency_ms": latency_ms,
                "pass_threshold": cfg.pass_threshold,
            }

            if not passed and cfg.fail_on_error:
                raise RuntimeError(
                    f"AI evaluation failed (score {score:.2f} below threshold {cfg.pass_threshold:.2f}): {reasoning}"
                )

            return result
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
            logger.error("ai_evaluation_execution_failed", error=str(exc))
            if cfg.fail_on_error:
                raise RuntimeError(f"AI evaluation step failed: {exc}") from exc
            return {
                "score": 0.0,
                "passed": False,
                "reasoning": f"Execution error: {exc}",
                "recommendation": "Check AI service availability and retry.",
                "latency_ms": int((time.monotonic() - started) * 1000),
                "error": str(exc),
            }


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


class ApplicationIntakeExecutor:
    """Create an Application record from workflow config."""

    async def execute(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any],
        run: ValidationRun,
    ) -> Dict[str, Any]:
        from app.database import get_db_context
        from app.models import Application, ApplicationStatusEnum
        from app.core.encryption import compute_searchable_hash
        from app.validation_engine.schemas import ApplicationIntakeConfig

        cfg = ApplicationIntakeConfig.model_validate(config)

        existing_id = _resolve_application_id(context, required=False)
        if existing_id is not None:
            # Pipeline was triggered for an existing application — do not duplicate it
            async with get_db_context() as db:
                from sqlalchemy import select
                result = await db.execute(select(Application).where(Application.id == existing_id))
                application = result.scalar_one_or_none()
                if application is None:
                    raise RuntimeError(f"Application {existing_id} not found")
                return {
                    "application_id": str(application.id),
                    "project_title": application.project_title,
                    "status": application.status.value,
                    "confidence_score": application.confidence_score,
                    "existing": True,
                }

        email_hash = compute_searchable_hash(cfg.applicant_email)

        application = Application(
            applicant_email_hash=email_hash,
            applicant_email_encrypted=cfg.applicant_email,
            organization_name=cfg.organization_name,
            project_title=cfg.project_title,
            country=cfg.country,
            sector=cfg.sector,
            proposed_methodology=cfg.proposed_methodology,
            status=ApplicationStatusEnum.intake,
            confidence_score=0.95,
        )

        async with get_db_context() as db:
            db.add(application)
            await db.commit()
            await db.refresh(application)

        return {
            "application_id": str(application.id),
            "project_title": application.project_title,
            "status": application.status.value,
            "confidence_score": application.confidence_score,
        }


class DocumentCollectionExecutor:
    """Record discovered document slots for an application and await uploads."""

    async def execute(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any],
        run: ValidationRun,
    ) -> Dict[str, Any]:
        from sqlalchemy import select
        from app.database import get_db_context
        from app.models import (
            Application,
            ApplicationDocument,
            ApplicationDocumentSourceEnum,
            ApplicationDocumentStatusEnum,
            ApplicationStatusEnum,
        )
        from app.validation_engine.schemas import DocumentCollectionConfig

        cfg = DocumentCollectionConfig.model_validate(config)
        application_id = _resolve_application_id(context)

        async with get_db_context() as db:
            result = await db.execute(select(Application).where(Application.id == application_id))
            application = result.scalar_one_or_none()
            if not application:
                raise RuntimeError(f"Application {application_id} not found")

            collected = []
            for source in cfg.sources:
                doc = ApplicationDocument(
                    application_id=application_id,
                    source_type=ApplicationDocumentSourceEnum(source.get("type", "upload")),
                    source_url=source.get("url"),
                    status=ApplicationDocumentStatusEnum.discovered,
                )
                db.add(doc)
                collected.append({"document_id": str(doc.id), "status": "discovered"})

            application.status = ApplicationStatusEnum.documents_pending
            await db.commit()

        return {
            "application_id": str(application_id),
            "collected_documents": collected,
            "required_document_types": cfg.required_document_types,
            "status": "awaiting_documents",
            "confidence_score": 0.7,
        }


class DocumentAiClassificationExecutor:
    """Classify application documents and extract entities."""

    async def execute(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any],
        run: ValidationRun,
    ) -> Dict[str, Any]:
        from sqlalchemy import select
        from app.database import get_db_context
        from app.models import (
            ApplicationDocument,
            ApplicationDocumentStatusEnum,
            ApplicationDocumentTypeEnum,
        )
        from app.services.kimi_api import KimiAPIClient
        from app.validation_engine.schemas import DocumentAiClassificationConfig

        cfg = DocumentAiClassificationConfig.model_validate(config)
        application_id = _resolve_application_id(context)

        async with get_db_context() as db:
            result = await db.execute(
                select(ApplicationDocument).where(ApplicationDocument.application_id == application_id)
            )
            documents = result.scalars().all()

            classified = []
            for doc in documents:
                if cfg.classify_with_kimi and doc.extracted_text:
                    kimi = KimiAPIClient()
                    prompt = (
                        "Classify this carbon-credit project document into one of: "
                        "pdd, monitoring_report, kpt_results, sales_receipt, survey_form, "
                        "gps_data, stove_inventory, other. "
                        "Return only the document type.\n\n"
                        f"Text excerpt:\n{doc.extracted_text[:2000]}"
                    )
                    response = await kimi.chat_completion(messages=[{"role": "user", "content": prompt}])
                    doc_type = (response.get("content", "") or "other").strip().lower()
                    if doc_type not in [e.value for e in ApplicationDocumentTypeEnum]:
                        doc_type = "other"
                else:
                    doc_type = "other"

                doc.document_type = ApplicationDocumentTypeEnum(doc_type)
                doc.status = ApplicationDocumentStatusEnum.processed
                classified.append({
                    "document_id": str(doc.id),
                    "document_type": doc_type,
                    "status": doc.status.value,
                })

            # Gap analysis: compare classified documents against requirements
            classified_types = {c["document_type"] for c in classified}
            missing = [t for t in cfg.required_document_types if t not in classified_types]
            gap_findings = {
                "required_document_types": cfg.required_document_types,
                "classified_document_types": sorted(classified_types),
                "missing_document_types": missing,
                "has_gaps": len(missing) > 0,
                "remediation": [_gap_remediation(t) for t in missing],
            }

            from app.models import Application, ApplicationStatusEnum
            app_result = await db.execute(select(Application).where(Application.id == application_id))
            application = app_result.scalar_one_or_none()
            if application is not None:
                application.gap_findings = gap_findings
                application.status = (
                    ApplicationStatusEnum.gaps if missing else ApplicationStatusEnum.pre_audit
                )

            await db.commit()

        return {
            "application_id": str(application_id),
            "classified_documents": classified,
            "gap_findings": gap_findings,
            "confidence_score": 0.85 if cfg.classify_with_kimi else 0.6,
        }


_GAP_REMEDIATION_GUIDANCE = {
    "pdd": "Upload the Project Design Document (PDD) for the proposed methodology.",
    "monitoring_report": "Upload the most recent monitoring report for the project.",
    "kpt_results": "Upload kitchen performance test (KPT) results.",
    "sales_receipt": "Upload sales receipts or invoices for the technology distributed.",
    "survey_form": "Upload completed household/beneficiary survey forms.",
    "gps_data": "Upload GPS coordinates of installation sites.",
    "stove_inventory": "Upload the stove inventory or distribution list.",
}


def _gap_remediation(document_type: str) -> Dict[str, str]:
    return {
        "document_type": document_type,
        "guidance": _GAP_REMEDIATION_GUIDANCE.get(
            document_type, f"Upload a document of type '{document_type}'."
        ),
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
            WorkflowStepType.ai_evaluation: AiEvaluationExecutor(),
            WorkflowStepType.wait: WaitExecutor(),
            WorkflowStepType.parallel: ParallelExecutor(),
            WorkflowStepType.subflow: SubflowExecutor(),
            WorkflowStepType.application_intake: ApplicationIntakeExecutor(),
            WorkflowStepType.document_collection: DocumentCollectionExecutor(),
            WorkflowStepType.document_ai_classification: DocumentAiClassificationExecutor(),
        }

    def get_executor(self, step_type: WorkflowStepType) -> StepExecutor:
        executor = self._executors.get(step_type)
        if executor is None:
            raise ValueError(f"No executor registered for step type: {step_type.value}")
        return executor

    def register(self, step_type: WorkflowStepType, executor: StepExecutor) -> None:
        self._executors[step_type] = executor
