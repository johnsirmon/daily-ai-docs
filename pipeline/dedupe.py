"""Deduplication: remove duplicate items by URL and title."""

from typing import Dict, List


def _norm_title(title: str) -> str:
    return title.lower().strip()


def dedupe(items: List[Dict]) -> List[Dict]:
    """Remove duplicates by canonical URL or exact (case-insensitive) title.

    When duplicates are found the item with the *higher* score is retained.
    Input order is otherwise preserved.
    """
    seen_urls: Dict[str, int] = {}   # url   -> index in result
    seen_titles: Dict[str, int] = {}  # title -> index in result
    result: List[Dict] = []

    for item in items:
        url = item.get("url", "")
        title = _norm_title(item.get("title", ""))

        # URL duplicate
        if url and url in seen_urls:
            idx = seen_urls[url]
            if item.get("score", 0) > result[idx].get("score", 0):
                result[idx] = item
                # Update title pointer if the replacement has a different title
                if title and title not in seen_titles:
                    seen_titles[title] = idx
            continue

        # Title duplicate (exact, case-insensitive)
        if title and title in seen_titles:
            idx = seen_titles[title]
            if item.get("score", 0) > result[idx].get("score", 0):
                result[idx] = item
                if url and url not in seen_urls:
                    seen_urls[url] = idx
            continue

        idx = len(result)
        result.append(item)
        if url:
            seen_urls[url] = idx
        if title:
            seen_titles[title] = idx

    return result
