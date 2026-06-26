"""Unified JSON contract v1 for REST and SSE."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"
HISTORY_CAP = 10


class ApiError(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class Envelope(BaseModel):
    schema_version: str = SCHEMA_VERSION
    type: str
    data: Optional[Any] = None
    error: Optional[ApiError] = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    message: str
    history: List[ChatMessage] = Field(default_factory=list)


class AgentSelectRequest(BaseModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    agent_id: str


class AgentPullRequest(BaseModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    agent_id: str


class RetrievalLimits(BaseModel):
    slots_per_doc: int = 2
    comparison_slots_per_doc: int = 3
    max_total_chunks: int = 8


class AgentProfile(BaseModel):
    id: str
    display_name: str
    ollama_tag: str
    role: Literal["chat", "embed"] = "chat"
    tier: str = "balanced"
    default: bool = False
    context_window_tokens: int = 8192
    max_history_messages: int = 10
    num_predict: int = 768
    temperature: float = 0.3
    min_ram_gb: float = 8
    min_vram_gb: Optional[float] = 4
    disk_gb: float = 2.0
    description: str = ""
    retrieval: RetrievalLimits = Field(default_factory=RetrievalLimits)
    capabilities: List[str] = Field(default_factory=list)


class AgentListItem(AgentProfile):
    installed: bool = False
    compatibility: Literal["compatible", "marginal", "incompatible", "unknown"] = "unknown"
    recommendation_score: float = 0.0


class SystemSpecs(BaseModel):
    os: str
    cpu: str
    ram_gb: float
    vram_gb: Optional[float] = None
    gpu_name: Optional[str] = None
    ollama_reachable: bool = False


class ContextBudget(BaseModel):
    history_cap: int
    history_used: int
    chunks_used: int
    max_total_chunks: int
    estimated_prompt_tokens: int


def envelope_ok(event_type: str, data: Any) -> Dict[str, Any]:
    return Envelope(type=event_type, data=data).model_dump()


def envelope_error(
    event_type: str, code: str, message: str, details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    return Envelope(
        type=event_type,
        data=None,
        error=ApiError(code=code, message=message, details=details),
    ).model_dump()


def sse_line(event_type: str, data: Any = None, error: Optional[ApiError] = None) -> str:
    payload = Envelope(type=event_type, data=data, error=error)
    return f"data: {json.dumps(payload.model_dump())}\n\n"
