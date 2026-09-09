"""Source adapter package for authoritative daily AI developer updates."""

from .github import collect_github_releases
from .feeds import collect_official_feeds
from .youtube import collect_youtube_digest

__all__ = ["collect_github_releases", "collect_official_feeds", "collect_youtube_digest"]
