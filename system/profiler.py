from __future__ import annotations

import os
import platform
import subprocess
from typing import Optional, Tuple

import httpx

from schemas.v1 import SystemSpecs

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def _detect_vram() -> Tuple[Optional[float], Optional[str]]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None, None
        line = result.stdout.strip().splitlines()[0]
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2:
            gpu_name = parts[0]
            vram_mb = float(parts[1])
            return round(vram_mb / 1024, 2), gpu_name
    except Exception:
        pass
    return None, None


def _ram_gb() -> float:
    try:
        import psutil

        return round(psutil.virtual_memory().total / (1024 ** 3), 2)
    except Exception:
        return 8.0


async def collect_system_specs() -> SystemSpecs:
    vram_gb, gpu_name = _detect_vram()
    ram_gb = _ram_gb()
    ollama_reachable = False

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            ollama_reachable = response.status_code == 200
    except Exception:
        ollama_reachable = False

    if vram_gb is None and platform.system() == "Darwin" and ram_gb:
        vram_gb = ram_gb
        gpu_name = gpu_name or "Apple Silicon (unified memory)"

    return SystemSpecs(
        os=f"{platform.system()} {platform.release()}",
        cpu=platform.processor() or platform.machine(),
        ram_gb=ram_gb,
        vram_gb=vram_gb,
        gpu_name=gpu_name,
        ollama_reachable=ollama_reachable,
    )
