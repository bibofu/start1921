from __future__ import annotations

import hmac
import logging
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import aclosing, asynccontextmanager
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from history_agent import __version__
from history_agent.answering.compression import maybe_compress_session
from history_agent.answering.context import (
    COOKIE_CHECK_NAME,
    ConversationMessage,
    ConversationStore,
    DuplicateRequest,
    QuotaExceeded,
    QuotaLimits,
    SessionBusy,
    SessionLimitExceeded,
    SessionNotFound,
    SessionRecord,
    VersionConflict,
    VisitorContext,
    build_prompt_context,
    hash_ip,
)
from history_agent.answering.models import AnswerResponse, QuestionRequest
from history_agent.answering.runtime import LLMRuntime, RequestBudget
from history_agent.answering.service import answer_question_async
from history_agent.answering.streaming import AnswerStreamEvent, stream_answer_question
from history_agent.config import Settings, get_settings
from history_agent.db import Database
from history_agent.db_backend import DATABASE_ERRORS
from history_agent.errors import ResearchDataError, RetrievalError
from history_agent.research.intersections import (
    PersonIntersectionResponse,
    get_person_intersections,
)
from history_agent.research.organization import (
    OrganizationRelationResponse,
    get_organization_relationships,
)
from history_agent.research.timeline import (
    PersonTimelineResponse,
    TimelineReviewStatus,
    get_person_timeline,
)
from history_agent.web.readiness import (
    _database_ready,
    keyword_index_ready,
    readiness_snapshot,
    vector_index_ready,
)

LOGGER = logging.getLogger(__name__)
SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
COOKIE_MAX_AGE = 365 * 24 * 60 * 60
UNDO_DAYS = 30
CSRF_HEADER = "X-CSRF-Token"


class SessionCreate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)


class SessionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    pinned: bool | None = None
    version: int | None = Field(default=None, ge=0)


class ClaimRequest(BaseModel):
    legacy_session_id: str = Field(
        min_length=16,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


def _session_payload(session: SessionRecord) -> dict[str, object]:
    return session.as_dict()


def _message_payload(message: ConversationMessage) -> dict[str, object]:
    return {
        "message_id": message.message_id,
        "role": message.role,
        "content": message.content,
        "status": message.status,
        "created_at": message.created_at,
    }


def _next_before(messages: list[ConversationMessage], limit: int) -> int | None:
    if len(messages) < limit or not messages:
        return None
    return messages[0].message_id


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    return request.client.host if request.client is not None else "unknown"


def _estimate_tokens(question: str) -> int:
    return max(1_000, min(48_000, len(question) * 3 + 2_000))


def _usage_from_response(response: AnswerResponse) -> tuple[int, int]:
    usage = response.llm_usage or {}
    return int(usage.get("prompt_tokens", 0) or 0), int(usage.get("completion_tokens", 0) or 0)


def _usage_from_event(data: dict[str, Any]) -> tuple[int, int]:
    usage = data.get("llm_usage") or {}
    if not isinstance(usage, dict):
        return 0, 0
    return int(usage.get("prompt_tokens", 0) or 0), int(usage.get("completion_tokens", 0) or 0)


def current_visitor(request: Request) -> VisitorContext:
    """FastAPI dependency populated by the visitor middleware."""

    visitor = getattr(request.state, "visitor", None)
    if not isinstance(visitor, VisitorContext):
        raise HTTPException(status_code=503, detail="会话服务暂不可用")
    return visitor


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    static_dir = files("history_agent.web").joinpath("static")
    conversations = ConversationStore(
        active_settings.conversation_database_target,
        pepper=active_settings.visitor_token_pepper.get_secret_value(),
    )
    quota_limits = QuotaLimits(
        enabled=active_settings.quota_enabled,
        visitor_daily_questions=active_settings.visitor_daily_questions,
        visitor_daily_tokens=active_settings.visitor_daily_tokens,
        ip_daily_questions=active_settings.ip_daily_questions,
        ip_daily_tokens=active_settings.ip_daily_tokens,
        global_daily_tokens=active_settings.global_daily_tokens,
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        runtime = LLMRuntime(active_settings.llm_max_concurrency)
        application.state.llm_runtime = runtime
        try:
            yield
        finally:
            await runtime.aclose()

    api = FastAPI(
        title="start1921 · 近现代史研究 Agent",
        version=__version__,
        description="Local evidence-grounded RAG for the 1921-1978 corpus.",
        lifespan=lifespan,
    )
    api.mount("/assets", StaticFiles(directory=str(static_dir)), name="assets")

    @api.middleware("http")
    async def visitor_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        if path.startswith("/assets/") or path in {"/app.css", "/app.js", "/api/health"}:
            return await call_next(request)
        pepper = active_settings.visitor_token_pepper.get_secret_value()
        ip_hash = hash_ip(_client_ip(request), pepper)
        request.state.ip_hash = ip_hash
        visitor: VisitorContext | None = None
        new_token: str | None = None
        try:
            token = request.cookies.get(active_settings.visitor_cookie_name)
            visitor = conversations.resolve_visitor(token) if token else None
            if visitor is None:
                visitor, new_token = conversations.create_visitor(
                    ip_hash=ip_hash,
                    user_agent_hash=hash_ip(request.headers.get("user-agent", ""), pepper),
                )
        except Exception:
            LOGGER.exception("visitor identity could not be resolved")
            if active_settings.environment == "production":
                visitor = None
            else:
                visitor = VisitorContext(
                    visitor_id="anonymous",
                    label="本地临时会话",
                    csrf_secret="",
                    ephemeral=True,
                )
        request.state.visitor = visitor
        response = await call_next(request)
        if new_token is not None:
            response.set_cookie(
                key=active_settings.visitor_cookie_name,
                value=new_token,
                max_age=COOKIE_MAX_AGE,
                httponly=True,
                secure=active_settings.visitor_cookie_secure,
                samesite="lax",
                path="/",
            )
        if COOKIE_CHECK_NAME not in request.cookies:
            response.set_cookie(
                key=COOKIE_CHECK_NAME,
                value="1",
                max_age=COOKIE_MAX_AGE,
                httponly=False,
                secure=active_settings.visitor_cookie_secure,
                samesite="lax",
                path="/",
            )
        return response

    def current_ip_hash(request: Request) -> str:
        return str(getattr(request.state, "ip_hash", "unknown"))

    def require_csrf(request: Request, visitor: VisitorContext) -> None:
        if not active_settings.csrf_enabled:
            return
        origin = request.headers.get("origin")
        if origin:
            host = request.headers.get("host", "")
            if urlsplit(origin).netloc != host:
                raise HTTPException(status_code=403, detail="请求来源校验失败")
        provided = request.headers.get(CSRF_HEADER, "")
        if not provided or not hmac.compare_digest(provided, visitor.csrf_secret):
            raise HTTPException(status_code=403, detail="CSRF 校验失败")

    def session_or_404(visitor: VisitorContext, session_id: str) -> SessionRecord:
        if visitor.ephemeral:
            raise HTTPException(status_code=503, detail="会话服务暂不可用")
        if SESSION_ID.fullmatch(session_id) is None:
            raise HTTPException(status_code=422, detail="invalid session_id")
        try:
            return conversations.get_session(visitor.visitor_id, session_id)
        except SessionNotFound as exc:
            raise HTTPException(status_code=404, detail="会话不存在") from exc

    def compress_session(visitor_id: str, session_id: str) -> None:
        try:
            maybe_compress_session(
                conversations,
                visitor_id,
                session_id,
                person_aliases_path=active_settings.person_aliases_path,
            )
        except Exception:
            LOGGER.exception("conversation compression failed")

    def with_session_context(
        visitor: VisitorContext,
        request: QuestionRequest,
        *,
        before_message_id: int | None = None,
    ) -> QuestionRequest:
        if request.session_id is None:
            return request
        if visitor.ephemeral:
            raise HTTPException(status_code=503, detail="会话服务暂不可用")
        session = session_or_404(visitor, request.session_id)
        del session
        summary = conversations.latest_summary(visitor.visitor_id, request.session_id)
        try:
            persisted = conversations.session_messages(
                visitor.visitor_id,
                request.session_id,
                after=summary.through_message_id if summary else None,
                before=before_message_id,
                limit=1_000,
                include_unfinished=False,
            )
        except SessionNotFound as exc:
            raise HTTPException(status_code=404, detail="会话不存在") from exc
        history = build_prompt_context(
            persisted,
            max_messages=active_settings.context_max_messages,
            max_chars=active_settings.context_max_chars,
            max_tokens=active_settings.context_max_tokens,
            summary=summary.content if summary else None,
        )
        return request.model_copy(update={"history": history})

    @api.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(
            str(static_dir.joinpath("index.html")), headers={"Cache-Control": "no-store"}
        )

    @api.get("/s/{session_id}", include_in_schema=False)
    def session_page(session_id: str) -> FileResponse:
        del session_id
        return FileResponse(
            str(static_dir.joinpath("index.html")), headers={"Cache-Control": "no-store"}
        )

    @api.get("/app.css", include_in_schema=False)
    def stylesheet() -> FileResponse:
        return FileResponse(
            str(static_dir.joinpath("app.css")),
            media_type="text/css",
            headers={"Cache-Control": "no-store"},
        )

    @api.get("/app.js", include_in_schema=False)
    def javascript() -> FileResponse:
        return FileResponse(
            str(static_dir.joinpath("app.js")),
            media_type="application/javascript",
            headers={"Cache-Control": "no-store"},
        )

    @api.get("/api/visitor")
    def visitor_info(
        visitor: Annotated[VisitorContext, Depends(current_visitor)],
    ) -> dict[str, object]:
        usage = {"questions": 0, "tokens": 0}
        if not visitor.ephemeral:
            try:
                usage = conversations.usage_snapshot(visitor.visitor_id)
            except Exception:
                LOGGER.exception("visitor quota could not be read")
        return {
            "visitor": {"label": visitor.label},
            "csrf_token": visitor.csrf_secret,
            "quota": {
                "daily_questions": active_settings.visitor_daily_questions,
                "used_today": usage["questions"],
                "tokens_used_today": usage["tokens"],
                "enabled": active_settings.quota_enabled and not visitor.ephemeral,
            },
            "limits": {
                "max_sessions": active_settings.max_sessions_per_visitor,
                "max_messages_per_session": active_settings.max_messages_per_session,
            },
        }

    @api.delete("/api/visitor/data")
    def delete_visitor_data(
        request: Request,
        visitor: Annotated[VisitorContext, Depends(current_visitor)],
    ) -> dict[str, object]:
        require_csrf(request, visitor)
        removed = conversations.delete_all(visitor.visitor_id)
        return {"deleted_sessions": removed}

    @api.get("/api/sessions")
    def list_sessions(
        visitor: Annotated[VisitorContext, Depends(current_visitor)],
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict[str, object]:
        items, has_more = conversations.list_sessions(
            visitor.visitor_id,
            limit=limit,
            offset=offset,
        )
        return {
            "items": [_session_payload(item) for item in items],
            "has_more": has_more,
            "offset": offset,
            "limit": limit,
        }

    @api.post("/api/sessions")
    def create_session(
        request: Request,
        visitor: Annotated[VisitorContext, Depends(current_visitor)],
        payload: SessionCreate | None = None,
    ) -> dict[str, object]:
        require_csrf(request, visitor)
        if visitor.ephemeral:
            raise HTTPException(status_code=503, detail="会话服务暂不可用")
        try:
            session_count = conversations.count_sessions(visitor.visitor_id)
            if session_count >= active_settings.max_sessions_per_visitor:
                raise SessionLimitExceeded("session limit")
            session = conversations.create_session(
                visitor.visitor_id,
                title=payload.title if payload else None,
            )
        except SessionLimitExceeded as exc:
            raise HTTPException(status_code=429, detail="会话数量已达上限") from exc
        return {"session": _session_payload(session)}

    @api.post("/api/sessions/claim")
    def claim_session(
        request: Request,
        payload: ClaimRequest,
        visitor: Annotated[VisitorContext, Depends(current_visitor)],
    ) -> dict[str, object]:
        require_csrf(request, visitor)
        try:
            session = conversations.claim_session(visitor.visitor_id, payload.legacy_session_id)
        except SessionNotFound as exc:
            raise HTTPException(status_code=404, detail="旧会话不存在或已被认领") from exc
        return {"session": _session_payload(session)}

    @api.get("/api/sessions/{session_id}")
    def get_session(
        session_id: str,
        visitor: Annotated[VisitorContext, Depends(current_visitor)],
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        before: Annotated[int | None, Query(ge=1)] = None,
    ) -> dict[str, object]:
        session = session_or_404(visitor, session_id)
        try:
            messages = conversations.session_messages(
                visitor.visitor_id,
                session_id,
                before=before,
                limit=limit,
                include_unfinished=True,
            )
        except SessionNotFound as exc:
            raise HTTPException(status_code=404, detail="会话不存在") from exc
        return {
            "session": _session_payload(session),
            "messages": [_message_payload(message) for message in messages],
            "next_before": _next_before(messages, limit),
        }

    @api.get("/api/sessions/{session_id}/messages")
    def get_session_messages(
        session_id: str,
        visitor: Annotated[VisitorContext, Depends(current_visitor)],
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        before: Annotated[int | None, Query(ge=1)] = None,
    ) -> dict[str, object]:
        session_or_404(visitor, session_id)
        try:
            messages = conversations.session_messages(
                visitor.visitor_id,
                session_id,
                before=before,
                limit=limit,
                include_unfinished=True,
            )
        except SessionNotFound as exc:
            raise HTTPException(status_code=404, detail="会话不存在") from exc
        return {
            "messages": [_message_payload(message) for message in messages],
            "next_before": _next_before(messages, limit),
        }

    @api.patch("/api/sessions/{session_id}")
    def update_session(
        session_id: str,
        request: Request,
        payload: SessionUpdate,
        visitor: Annotated[VisitorContext, Depends(current_visitor)],
    ) -> dict[str, object]:
        require_csrf(request, visitor)
        session = session_or_404(visitor, session_id)
        if payload.version is not None and payload.version != session.version:
            raise HTTPException(status_code=409, detail="会话已被其他标签页修改")
        try:
            if payload.title is not None:
                session = conversations.rename_session(
                    visitor.visitor_id, session_id, payload.title, expected_version=payload.version
                )
            if payload.pinned is not None:
                session = conversations.set_pinned(
                    visitor.visitor_id, session_id, payload.pinned
                )
        except VersionConflict as exc:
            raise HTTPException(status_code=409, detail="会话已被其他标签页修改") from exc
        except SessionNotFound as exc:
            raise HTTPException(status_code=404, detail="会话不存在") from exc
        return {"session": _session_payload(session)}

    @api.delete("/api/sessions/{session_id}")
    def delete_session(
        session_id: str,
        request: Request,
        visitor: Annotated[VisitorContext, Depends(current_visitor)],
    ) -> dict[str, object]:
        require_csrf(request, visitor)
        try:
            session = conversations.soft_delete(visitor.visitor_id, session_id)
        except SessionNotFound as exc:
            raise HTTPException(status_code=404, detail="会话不存在") from exc
        undo_until = (datetime.now(UTC) + timedelta(days=UNDO_DAYS)).isoformat()
        return {"deleted": True, "session": _session_payload(session), "undo_until": undo_until}

    @api.post("/api/sessions/{session_id}/restore")
    def restore_session(
        session_id: str,
        request: Request,
        visitor: Annotated[VisitorContext, Depends(current_visitor)],
    ) -> dict[str, object]:
        require_csrf(request, visitor)
        try:
            session = conversations.restore_session(visitor.visitor_id, session_id)
        except SessionNotFound as exc:
            raise HTTPException(status_code=404, detail="会话不存在或未删除") from exc
        return {"session": _session_payload(session)}

    @api.post("/api/questions", response_model=AnswerResponse)
    async def question(
        payload: QuestionRequest,
        request: Request,
        visitor: Annotated[VisitorContext, Depends(current_visitor)],
    ) -> AnswerResponse:
        require_csrf(request, visitor)
        reservation = None
        start = None
        settled = False
        try:
            if payload.session_id is not None and visitor.ephemeral:
                raise HTTPException(status_code=503, detail="会话服务暂不可用")
            if not visitor.ephemeral:
                reservation = conversations.reserve_quota(
                    visitor.visitor_id,
                    current_ip_hash(request),
                    _estimate_tokens(payload.question),
                    quota_limits,
                )
            if payload.session_id is not None:
                try:
                    start = conversations.begin_question(
                        visitor.visitor_id,
                        payload.session_id,
                        payload.question,
                        payload.client_request_id,
                    )
                except SessionNotFound as exc:
                    raise HTTPException(status_code=404, detail="会话不存在") from exc
                except SessionBusy as exc:
                    raise HTTPException(status_code=409, detail="当前会话正在生成") from exc
                except DuplicateRequest as exc:
                    raise HTTPException(status_code=409, detail="重复的请求") from exc
            contextual_request = with_session_context(
                visitor, payload, before_message_id=start.message_id if start else None
            )
            runtime = getattr(api.state, "llm_runtime", None)
            if runtime is None:
                response = await answer_question_async(active_settings, contextual_request)
            else:
                response = await answer_question_async(
                    active_settings,
                    contextual_request,
                    runtime,
                    RequestBudget.start(active_settings.request_timeout_seconds),
                )
            if start is not None and payload.session_id is not None:
                saved = conversations.complete_question(
                    visitor.visitor_id,
                    payload.session_id,
                    start.message_id,
                    response.answer,
                    start.run_id,
                    client_request_id=payload.client_request_id,
                )
                if saved:
                    compress_session(visitor.visitor_id, payload.session_id)
            prompt_tokens, completion_tokens = _usage_from_response(response)
            conversations.settle_quota(
                reservation,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            settled = True
            return response
        except QuotaExceeded as exc:
            raise HTTPException(
                status_code=429,
                detail="今日提问额度已用完",
                headers={"Retry-After": str(exc.retry_after), "X-Quota-Reset": exc.reset_at},
            ) from exc
        except RetrievalError as exc:
            if start is not None and payload.session_id is not None:
                conversations.abort_question(
                    visitor.visitor_id,
                    payload.session_id,
                    start.message_id,
                    start.run_id,
                    failed=True,
                )
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except HTTPException:
            if start is not None and payload.session_id is not None:
                conversations.abort_question(
                    visitor.visitor_id,
                    payload.session_id,
                    start.message_id,
                    start.run_id,
                    failed=True,
                )
            raise
        except Exception:
            if start is not None and payload.session_id is not None:
                conversations.abort_question(
                    visitor.visitor_id,
                    payload.session_id,
                    start.message_id,
                    start.run_id,
                    failed=True,
                )
            raise
        finally:
            if not settled:
                conversations.release_quota(reservation)

    @api.post("/api/questions/stream")
    async def question_stream(
        payload: QuestionRequest,
        request: Request,
        visitor: Annotated[VisitorContext, Depends(current_visitor)],
    ) -> StreamingResponse:
        require_csrf(request, visitor)
        reservation = None
        start = None
        try:
            if payload.session_id is not None and visitor.ephemeral:
                raise HTTPException(status_code=503, detail="会话服务暂不可用")
            if not visitor.ephemeral:
                reservation = conversations.reserve_quota(
                    visitor.visitor_id,
                    current_ip_hash(request),
                    _estimate_tokens(payload.question),
                    quota_limits,
                )
            if payload.session_id is not None:
                try:
                    start = conversations.begin_question(
                        visitor.visitor_id,
                        payload.session_id,
                        payload.question,
                        payload.client_request_id,
                    )
                except SessionNotFound as exc:
                    raise HTTPException(status_code=404, detail="会话不存在") from exc
                except SessionBusy as exc:
                    raise HTTPException(status_code=409, detail="当前会话正在生成") from exc
                except DuplicateRequest as exc:
                    raise HTTPException(status_code=409, detail="重复的请求") from exc
        except QuotaExceeded as exc:
            raise HTTPException(
                status_code=429,
                detail="今日提问额度已用完",
                headers={"Retry-After": str(exc.retry_after), "X-Quota-Reset": exc.reset_at},
            ) from exc
        except Exception:
            conversations.release_quota(reservation)
            raise

        async def events() -> AsyncIterator[str]:
            completed = False
            settled = False
            try:
                contextual_request = with_session_context(
                    visitor, payload, before_message_id=start.message_id if start else None
                )
                runtime = getattr(api.state, "llm_runtime", None)
                answers = (
                    stream_answer_question(active_settings, contextual_request)
                    if runtime is None
                    else stream_answer_question(
                        active_settings,
                        contextual_request,
                        runtime,
                        RequestBudget.start(active_settings.request_timeout_seconds),
                    )
                )
                async with aclosing(answers) as stream:
                    async for event in stream:
                        if event.event == "done":
                            data = event.data
                            if start is not None and payload.session_id is not None:
                                completed = conversations.complete_question(
                                    visitor.visitor_id,
                                    payload.session_id,
                                    start.message_id,
                                    str(data["answer"]),
                                    start.run_id,
                                    client_request_id=payload.client_request_id,
                                )
                            else:
                                completed = True
                            if completed and start is not None and payload.session_id is not None:
                                compress_session(visitor.visitor_id, payload.session_id)
                            prompt_tokens, completion_tokens = _usage_from_event(data)
                            conversations.settle_quota(
                                reservation,
                                prompt_tokens=prompt_tokens,
                                completion_tokens=completion_tokens,
                            )
                            settled = True
                        yield event.encode()
            except RetrievalError:
                if start is not None and payload.session_id is not None:
                    conversations.abort_question(
                        visitor.visitor_id,
                        payload.session_id,
                        start.message_id,
                        start.run_id,
                        failed=True,
                    )
                yield AnswerStreamEvent(
                    "error", {"message": "本地检索暂不可用，请检查索引后重试。"}
                ).encode()
            except Exception:
                LOGGER.exception("streaming answer failed")
                if start is not None and payload.session_id is not None:
                    conversations.abort_question(
                        visitor.visitor_id,
                        payload.session_id,
                        start.message_id,
                        start.run_id,
                        failed=True,
                    )
                yield AnswerStreamEvent(
                    "error", {"message": "问答服务暂时不可用，请重试。"}
                ).encode()
            finally:
                if start is not None and payload.session_id is not None and not completed:
                    conversations.abort_question(
                        visitor.visitor_id,
                        payload.session_id,
                        start.message_id,
                        start.run_id,
                    )
                if not settled:
                    conversations.release_quota(reservation)

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
        )

    @api.get("/api/health")
    def health() -> dict[str, object]:
        try:
            database_ready = _database_ready(active_settings.database_target)
        except (OSError, *DATABASE_ERRORS):
            database_ready = False
        indexes = {
            "keyword": keyword_index_ready(active_settings),
            "vector": vector_index_ready(active_settings),
        }
        return {
            "status": "ok",
            "version": __version__,
            "rag_framework": "llamaindex",
            "database_backend": active_settings.database_backend,
            "database_ready": database_ready,
            "conversation_database_backend": active_settings.conversation_database_backend,
            "keyword_database_backend": active_settings.keyword_database_backend,
            "vector_database_backend": active_settings.vector_database_backend,
            "rag_execution_paths": ["llamaindex"],
            "llamaindex_components": [
                "workflow",
                "query_bundle",
                "retriever",
                "node_postprocessor",
                "llm_adapter",
                "callback_manager",
                "output_parser",
                "prompt_template",
                "response_synthesizer",
            ],
            "indexes": indexes,
            "llm_enabled": active_settings.llm_enabled,
            "llm_provider": active_settings.llm_provider,
            "llm_model": active_settings.llm_model,
            "llm_thinking": active_settings.llm_thinking,
            "llm_query_planning": active_settings.llm_query_planning,
            "llm_query_planner_model": active_settings.llm_query_planner_model,
            "llm_retrieval_reflection": active_settings.llm_retrieval_reflection,
            "answer_workflow": "plan_and_execute",
            "research_range": [
                active_settings.research_start.year,
                active_settings.research_end.year,
            ],
        }

    @api.get("/api/ready")
    def ready() -> JSONResponse:
        snapshot = readiness_snapshot(active_settings)
        status_code = 200 if snapshot["status"] == "ready" else 503
        return JSONResponse(snapshot, status_code=status_code)

    @api.get("/api/people/{person_id}/timeline", response_model=PersonTimelineResponse)
    def person_timeline(
        person_id: str,
        start_year: Annotated[int | None, Query(ge=1, le=9999)] = None,
        end_year: Annotated[int | None, Query(ge=1, le=9999)] = None,
        event_type: Annotated[list[str] | None, Query()] = None,
        review_status: Annotated[list[TimelineReviewStatus] | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> PersonTimelineResponse:
        lower = active_settings.research_start.year
        upper = active_settings.research_end.year
        if start_year is not None and not lower <= start_year <= upper:
            raise HTTPException(
                status_code=422,
                detail=f"start_year must be within the research range {lower}-{upper}",
            )
        if end_year is not None and not lower <= end_year <= upper:
            raise HTTPException(
                status_code=422,
                detail=f"end_year must be within the research range {lower}-{upper}",
            )
        try:
            return get_person_timeline(
                Database(active_settings.database_target),
                person_id=person_id,
                start_year=start_year,
                end_year=end_year,
                event_types=event_type,
                review_statuses=review_status,
                limit=limit,
                offset=offset,
            )
        except ResearchDataError as exc:
            status_code = 404 if str(exc).startswith("unknown person_id") else 400
            raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    @api.get(
        "/api/people/{person_id}/intersections/{other_person_id}",
        response_model=PersonIntersectionResponse,
    )
    def person_intersections(
        person_id: str,
        other_person_id: str,
        start_year: Annotated[int | None, Query(ge=1, le=9999)] = None,
        end_year: Annotated[int | None, Query(ge=1, le=9999)] = None,
        event_type: Annotated[list[str] | None, Query()] = None,
        review_status: Annotated[list[TimelineReviewStatus] | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> PersonIntersectionResponse:
        lower, upper = active_settings.research_start.year, active_settings.research_end.year
        for value in (start_year, end_year):
            if value is not None and not lower <= value <= upper:
                raise HTTPException(422, f"year must be within the research range {lower}-{upper}")
        try:
            return get_person_intersections(
                Database(active_settings.database_target),
                person_id=person_id,
                other_person_id=other_person_id,
                start_year=start_year if start_year is not None else lower,
                end_year=end_year if end_year is not None else upper,
                event_types=event_type,
                review_statuses=review_status,
                limit=limit,
                offset=offset,
            )
        except ResearchDataError as exc:
            status_code = 404 if str(exc).startswith("unknown person_id") else 400
            raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    @api.get(
        "/api/people/{person_id}/relationships",
        response_model=OrganizationRelationResponse,
    )
    def person_relationships(
        person_id: str,
        at: Annotated[str | None, Query()] = None,
        relation_type: Annotated[list[str] | None, Query()] = None,
        review_status: Annotated[list[str] | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> OrganizationRelationResponse:
        if at is not None:
            try:
                year = int(at[:4])
            except (TypeError, ValueError) as exc:
                raise HTTPException(422, "at must begin with a four-digit year") from exc
            lower, upper = active_settings.research_start.year, active_settings.research_end.year
            if not lower <= year <= upper:
                raise HTTPException(422, f"at must be within the research range {lower}-{upper}")
        try:
            return get_organization_relationships(
                Database(active_settings.database_target),
                person_id=person_id,
                at=at,
                relation_types=relation_type,
                review_statuses=review_status,
                limit=limit,
                offset=offset,
            )
        except ResearchDataError as exc:
            status_code = 404 if str(exc).startswith("unknown person_id") else 400
            raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    return api


app = create_app()
