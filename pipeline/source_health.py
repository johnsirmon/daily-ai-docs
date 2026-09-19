"""Keep per-candidate diagnostics from changing the configured-source quorum."""

from typing import Dict


def primary_source_health(health: Dict[str, str]) -> Dict[str, str]:
    return {
        name: status for name, status in health.items()
        if ":detail:" not in name
        and not name.startswith("research:arxiv:")
        and not name.startswith("youtube:")
    }


def failed_source_health(health: Dict[str, str]) -> tuple[list[str], list[str]]:
    """Return failed primary and supplementary source names separately."""
    primary = primary_source_health(health)
    failed_primary = [
        name for name, status in primary.items() if not status.startswith("ok:")
    ]
    failed_supplementary = [
        name for name, status in health.items()
        if name not in primary and ":detail:" not in name and not status.startswith("ok:")
    ]
    return failed_primary, failed_supplementary
