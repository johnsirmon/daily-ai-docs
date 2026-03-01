"""Deduplication: remove duplicate items by repo name."""

from typing import Dict, List


def dedupe(items: List[Dict]) -> List[Dict]:
    """Remove duplicate items by repo name, keeping highest-starred entry.

    Input order is otherwise preserved.
    """
    seen: Dict[str, int] = {}  # repo -> index in result
    result: List[Dict] = []

    for item in items:
        repo = item.get("repo", "")
        if repo and repo in seen:
            idx = seen[repo]
            if item.get("stars", 0) > result[idx].get("stars", 0):
                result[idx] = item
            continue
        idx = len(result)
        result.append(item)
        if repo:
            seen[repo] = idx

    return result

