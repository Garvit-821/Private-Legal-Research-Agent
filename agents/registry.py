from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Set

import httpx

from agents.compatibility import compatibility_label, recommendation_score
from schemas.v1 import AgentListItem, AgentProfile, SystemSpecs

CATALOG_PATH = Path(__file__).resolve().parent / "catalog.json"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

_catalog_cache: Optional[List[AgentProfile]] = None


def load_catalog() -> List[AgentProfile]:
    global _catalog_cache
    if _catalog_cache is not None:
        return _catalog_cache

    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    _catalog_cache = [AgentProfile(**item) for item in raw.get("agents", []) if item.get("role") == "chat"]
    return _catalog_cache


def get_embed_profile() -> AgentProfile:
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    for item in raw.get("agents", []):
        if item.get("role") == "embed" and item.get("default"):
            return AgentProfile(**item)
    return AgentProfile(
        id="nomic-embed-text",
        display_name="Nomic Embed Text",
        ollama_tag="nomic-embed-text",
        role="embed",
        tier="embed",
        default=True,
        min_vram_gb=None,
        description="Default embedding model",
    )


def get_chat_profile(agent_id: str) -> Optional[AgentProfile]:
    for profile in load_catalog():
        if profile.id == agent_id:
            return profile
    return None


async def fetch_installed_tags() -> Set[str]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            response.raise_for_status()
            payload = response.json()
            names: Set[str] = set()
            for model in payload.get("models", []):
                name = model.get("name", "")
                if name:
                    names.add(name)
                    names.add(name.split(":")[0])
            return names
    except Exception:
        return set()


def is_installed(tag: str, installed: Set[str]) -> bool:
    if tag in installed:
        return True
    base = tag.split(":")[0]
    return any(name == tag or name.startswith(f"{base}:") for name in installed)


def build_agent_list(specs: SystemSpecs, installed: Set[str]) -> Dict[str, List[AgentListItem]]:
    items: List[AgentListItem] = []
    for profile in load_catalog():
        installed_flag = is_installed(profile.ollama_tag, installed)
        item = AgentListItem(
            **profile.model_dump(),
            installed=installed_flag,
            compatibility=compatibility_label(specs, profile),
            recommendation_score=recommendation_score(specs, profile, installed_flag),
        )
        items.append(item)

    recommended = sorted(
        [item for item in items if item.compatibility != "incompatible"],
        key=lambda x: x.recommendation_score,
        reverse=True,
    )[:5]

    installed_items = [item for item in items if item.installed]
    library = sorted(items, key=lambda x: (x.tier, x.display_name))

    return {
        "recommended": recommended,
        "installed": installed_items,
        "library": library,
    }
