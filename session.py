"""Runtime session state for documents and agent selection."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

DEFAULT_CHAT_AGENT = os.getenv("CORTEX_DEFAULT_CHAT_MODEL", "qwen2.5:3b")
DEFAULT_EMBED_AGENT = os.getenv("CORTEX_EMBED_MODEL", "nomic-embed-text")
MAX_HISTORY_MESSAGES = int(os.getenv("CORTEX_HISTORY_LIMIT", "10"))
MAX_DOCUMENTS = int(os.getenv("CORTEX_MAX_DOCUMENTS", "5"))


class RuntimeSession:
  def __init__(self) -> None:
    self.documents: Dict[str, Dict[str, Any]] = {}
    self.active_filename: Optional[str] = None
    self.chat_agent_id: str = DEFAULT_CHAT_AGENT
    self.embed_agent_id: str = DEFAULT_EMBED_AGENT
    self.max_history_messages: int = MAX_HISTORY_MESSAGES


from agents.registry import get_embed_profile

runtime = RuntimeSession()
_embed_defaults = get_embed_profile()
runtime.embed_agent_id = _embed_defaults.ollama_tag
