from __future__ import annotations

from typing import Literal

from schemas.v1 import AgentProfile, SystemSpecs


def compatibility_label(
    specs: SystemSpecs, profile: AgentProfile
) -> Literal["compatible", "marginal", "incompatible", "unknown"]:
    if profile.min_vram_gb is None:
        if specs.ram_gb < profile.min_ram_gb:
            return "incompatible"
        if specs.ram_gb < profile.min_ram_gb * 1.15:
            return "marginal"
        return "compatible"

    if specs.ram_gb < profile.min_ram_gb:
        return "incompatible"

    if specs.vram_gb is None:
        if specs.ram_gb < profile.min_ram_gb * 1.25:
            return "marginal"
        return "unknown"

    if specs.vram_gb < profile.min_vram_gb:
        return "incompatible"
    if specs.vram_gb < profile.min_vram_gb * 1.15 or specs.ram_gb < profile.min_ram_gb * 1.15:
        return "marginal"
    return "compatible"


def recommendation_score(
    specs: SystemSpecs,
    profile: AgentProfile,
    installed: bool,
) -> float:
    label = compatibility_label(specs, profile)
    if label == "incompatible":
        return 0.0

    score = 50.0
    if label == "compatible":
        score += 25.0
    elif label == "marginal":
        score += 10.0
    else:
        score += 15.0

    if installed:
        score += 25.0
    if profile.default:
        score += 10.0
    if profile.tier == "lightweight" and specs.ram_gb <= 12:
        score += 10.0
    if profile.tier == "balanced" and specs.ram_gb >= 16:
        score += 10.0
    return round(min(score, 100.0), 2)
