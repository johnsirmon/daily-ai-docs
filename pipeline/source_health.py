"""Keep per-candidate diagnostics from changing the configured-source quorum."""

from typing import Dict


def primary_source_health(health: Dict[str, str]) -> Dict[str, str]:
    return {
        name: status for name, status in health.items()
        if ":detail:" not in name and not name.startswith("research:arxiv:")
    }
