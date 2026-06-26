from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from schemas.v1 import AgentProfile, ContextBudget, HISTORY_CAP
from session import runtime


def history_cap_for_profile(profile: AgentProfile) -> int:
    return min(runtime.max_history_messages, HISTORY_CAP, profile.max_history_messages)


def trim_history(raw_history: List[Dict[str, str]], profile: AgentProfile) -> List[Dict[str, str]]:
    cap = history_cap_for_profile(profile)
    return raw_history[-cap:]


def to_langchain_messages(history: List[Dict[str, str]]) -> List[BaseMessage]:
    messages: List[BaseMessage] = []
    for msg in history:
        if msg.get("role") == "user":
            messages.append(HumanMessage(content=msg.get("content", "")))
        elif msg.get("role") == "assistant":
            messages.append(AIMessage(content=msg.get("content", "")))
    return messages


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def apply_chunk_budget(
    matched_chunks: List[Dict[str, Any]],
    profile: AgentProfile,
    context_text: str,
    history: List[Dict[str, str]],
) -> tuple[List[Dict[str, Any]], ContextBudget]:
    max_chunks = profile.retrieval.max_total_chunks
    trimmed = matched_chunks[:max_chunks]

    history_tokens = sum(estimate_tokens(m.get("content", "")) for m in history)
    chunk_tokens = estimate_tokens(context_text)
    system_reserve = 800
    output_reserve = profile.num_predict
    estimated = history_tokens + chunk_tokens + system_reserve + output_reserve

    budget = ContextBudget(
        history_cap=history_cap_for_profile(profile),
        history_used=len(history),
        chunks_used=len(trimmed),
        max_total_chunks=max_chunks,
        estimated_prompt_tokens=estimated,
    )
    return trimmed, budget


def shrink_history_for_budget(
    history: List[Dict[str, str]],
    profile: AgentProfile,
    context_text: str,
    max_window: int,
) -> List[Dict[str, str]]:
    working = list(history)
    reserve = profile.num_predict + 800
    while working and (
        sum(estimate_tokens(m.get("content", "")) for m in working)
        + estimate_tokens(context_text)
        + reserve
        > max_window
    ):
        working.pop(0)
    return working
