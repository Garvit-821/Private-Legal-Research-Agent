from __future__ import annotations

import json
import uuid
from typing import Any, AsyncIterator, Dict, Optional

import httpx

from schemas.v1 import sse_line

OLLAMA_BASE_URL = __import__("os").getenv("OLLAMA_BASE_URL", "http://localhost:11434")

_pull_jobs: Dict[str, Dict[str, Any]] = {}


def create_pull_job(agent_id: str, ollama_tag: str) -> str:
    job_id = str(uuid.uuid4())
    _pull_jobs[job_id] = {
        "job_id": job_id,
        "agent_id": agent_id,
        "ollama_tag": ollama_tag,
        "status": "running",
        "progress": 0,
        "message": "Starting download",
    }
    return job_id


def get_pull_job(job_id: str) -> Optional[Dict[str, Any]]:
    return _pull_jobs.get(job_id)


async def stream_ollama_pull(ollama_tag: str, job_id: str) -> AsyncIterator[str]:
    job = _pull_jobs.get(job_id)
    if not job:
        yield sse_line("agent.pull.error", error=_api_error("JOB_NOT_FOUND", "Pull job not found"))
        return

    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_BASE_URL}/api/pull",
                json={"name": ollama_tag, "stream": True},
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    payload = json.loads(line)
                    status = payload.get("status", "")
                    completed = payload.get("completed")
                    total = payload.get("total")
                    progress = 0
                    if completed is not None and total:
                        progress = int((completed / total) * 100)
                    job["progress"] = progress
                    job["message"] = status
                    yield sse_line(
                        "agent.pull.progress",
                        {
                            "job_id": job_id,
                            "progress": progress,
                            "status": status,
                        },
                    )

        job["status"] = "completed"
        job["progress"] = 100
        yield sse_line("agent.pull.done", {"job_id": job_id, "ollama_tag": ollama_tag})
    except Exception as exc:
        job["status"] = "failed"
        job["message"] = str(exc)
        yield sse_line(
            "agent.pull.error",
            error=_api_error("PULL_FAILED", str(exc), {"job_id": job_id}),
        )


def _api_error(code: str, message: str, details: Optional[Dict[str, Any]] = None):
    from schemas.v1 import ApiError

    return ApiError(code=code, message=message, details=details)
