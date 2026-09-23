"""Render the README.md from collected pipeline data."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from .schema import source_display_label


def _trend_emoji(trend: str) -> str:
    return {"rising": "📈", "falling": "📉", "flat": "➡️"}.get(trend, "")


def topic_anchor_markup(topic_id: str) -> str:
    """Return explicit HTML anchor markup for stable topic links."""
    return f'<a id="{topic_id}"></a>'


def render_readme(topics_data: List[Dict], lookback_days: int = 14, research_report: Dict | None = None) -> str:
    """Build the full README content string from processed topic data."""
    now = datetime.now(tz=timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    generated = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    lines: List[str] = [
        f"# AI Skills Radar — {date_str}",
        "",
        f"_Updated: {generated} | Covers last {lookback_days} days_",
        "",
        "> Auto-generated. To refresh, go to **Actions → Update AI Skills Radar → Run workflow**.",
        "",
        "## Topics",
        "",
    ]

    # TOC
    for t in topics_data:
        anchor = t["id"]
        lines.append(f"- [{t['display']}](#{anchor})")
    lines += ["", "---", ""]

    # Podcast subscribe block
    feed_url = "https://johnsirmon.github.io/daily-ai-docs/podcast.xml"
    lines += [
        "## 🎙️ Podcast",
        "",
        "Listen to the weekly audio digest — auto-generated from this README.",
        "",
        f"[▶ Add to Apple Podcasts](podcast://{feed_url.split('://', 1)[1]})&nbsp;&nbsp;"
        f"[▶ Open in Overcast](https://overcast.fm/itunes?url={feed_url})&nbsp;&nbsp;"
        f"[▶ Open in Pocket Casts](https://pca.st/itunes?feed={feed_url})",
        "",
        "**Or paste this feed URL into any podcast app:**",
        "",
        "```",
        feed_url,
        "```",
        "",
        "---",
        "",
    ]

    # This Week's Story — cross-topic narrative from research summariser
    week_story = (research_report or {}).get("week_story", "")
    if week_story:
        lines += ["## 🗞️ This Week's Story", "", week_story, "", "---", ""]

    # Per-topic sections
    for t in topics_data:
        lines.append(topic_anchor_markup(t["id"]))
        lines.append(f"## {t['display']}")
        lines.append("")

        repos = [r for r in t.get("items", []) if r["type"] == "trending"]
        releases = [r for r in t.get("items", []) if r["type"] == "release"]
        deep_dives: List[Dict] = t.get("deep_dives", [])  # list of {repo, prose}
        action_items: List[str] = t.get("action_items", [])
        community_pulse: str = t.get("community_pulse", "")

        # --- Why / Learn header ---
        if t.get("why"):
            lines += [
                f"> **Why it matters:** {t['why']}",
                ">",
                f"> **What to learn:** {t['learn']}",
                "",
            ]

        # --- Overview narrative ---
        if t.get("summary"):
            lines += ["### Overview", "", t["summary"], ""]

        # --- Repo Deep Dives ---
        if deep_dives:
            lines += ["### 🔍 Repo Deep Dives", ""]
            for dd in deep_dives:
                repo_name = dd.get("repo", "")
                prose = dd.get("prose", "")
                # Find matching stats from repos list
                stats = next((r for r in repos if r["repo"] == repo_name), {})
                lines.append(f"#### `{repo_name}`")
                lines.append("")
                if stats:
                    trend = stats.get("commit_trend", "")
                    trend_icon = _trend_emoji(trend)
                    stat_parts = [f"⭐ {stats.get('stars', 0):,}"]
                    if stats.get("language"):
                        stat_parts.append(stats["language"])
                    if stats.get("forks"):
                        stat_parts.append(f"{stats['forks']:,} forks")
                    if stats.get("open_issues") is not None:
                        stat_parts.append(f"{stats['open_issues']} issues")
                    if stats.get("prs_merged_14d"):
                        stat_parts.append(f"{stats['prs_merged_14d']} PRs merged")
                    if trend:
                        stat_parts.append(f"{trend_icon} {trend}")
                    lines.append(f"_{' · '.join(stat_parts)}_")
                    lines.append("")
                if prose:
                    lines += [prose, ""]

        # --- Community Pulse ---
        if community_pulse:
            lines += ["### 📊 Community Pulse", "", community_pulse, ""]

        # --- Action Items ---
        if action_items:
            lines += ["### ✅ Action Items This Week", ""]
            for item in action_items:
                lines.append(f"- {item}")
            lines.append("")

        # --- Quick Reference table ---
        if repos:
            lines += [
                "### 🌱 New & Rising Repos",
                "",
                "| Repo | Stars | Forks | Issues | Language | Trend |",
                "|------|-------|-------|--------|----------|-------|",
            ]
            for r in repos:
                trend = r.get("commit_trend", "")
                trend_icon = _trend_emoji(trend)
                lines.append(
                    f"| [{r['repo']}]({r['url']}) "
                    f"| ⭐ {r['stars']:,} "
                    f"| {r.get('forks', '—')} "
                    f"| {r.get('open_issues', '—')} "
                    f"| {r.get('language') or '—'} "
                    f"| {trend_icon} {trend} |"
                )
            lines.append("")

        # --- Releases table ---
        if releases:
            lines += [
                "### 🚀 Recent Releases",
                "",
                "| Repo | Version | Date | Highlights |",
                "|------|---------|------|------------|",
            ]
            for r in releases:
                highlights = (r.get("notes") or "—")[:120].replace("\n", " ").replace("|", "\\|")
                reactions = r.get("reactions", 0)
                react_str = f" ({reactions} 👍)" if reactions else ""
                lines.append(
                    f"| [{r['repo']}]({r['url']}) "
                    f"| `{r['version']}` "
                    f"| {r['published_at']}{react_str} "
                    f"| {highlights} |"
                )
            lines.append("")

        if not repos and not releases:
            lines += ["_No recent activity detected._", ""]

        lines += ["---", ""]

    lines.append(
        "_[Pipeline source](.github/workflows/update-radar.yml) · "
        "[Config](topics/topics.yaml)_"
    )

    return "\n".join(lines) + "\n"


def write_readme(
    topics_data: List[Dict],
    lookback_days: int = 14,
    path: str = "README.md",
    research_report: Dict | None = None,
) -> Path:
    """Write rendered README.md and return its Path."""
    content = render_readme(topics_data, lookback_days, research_report=research_report)
    out = Path(path)
    out.write_text(content, encoding="utf-8")
    return out


def render_manifest_readme(manifest, feed_url: str | None = None) -> str:
    """Render the current brief and durable project overview from one manifest."""
    manifest.validate(require_audio=False)
    feed_url = feed_url or "https://johnsirmon.github.io/daily-ai-docs/podcast.xml"
    lines = [
        f"# Daily AI Developer Brief — {manifest.published_at[:10]}",
        "",
        '<p align="center">',
        '  <img src="assets/ai-update-wave.png" width="560" '
        'alt="An exhausted developer outrunning a tidal wave of AI tools and updates">',
        "</p>",
        '<p align="center"><em>Keep up with AI developer technology without being flattened by the update wave.</em></p>',
        "",
        "A source-backed briefing for AI developers: what changes your work, what is worth trying, and what to ignore.",
        "",
        "## Podcast",
        "",
        f"Intended subscriber feed: `{feed_url}`",
        "",
        "Publication is confirmed only after the subscriber feed, audio, and artwork pass delivery checks.",
        "",
        "Once the feed is live, open Apple Podcasts on iPhone → Library → Follow a Show by URL and paste it. CarPlay uses the followed show through Apple Podcasts; device playback still requires verification.",
        "",
        "See [operations and setup](docs/OPERATIONS.md#github-setup) for deployment status and setup.",
        "",
        "## How it works",
        "",
        "1. Public primary sources are collected with per-source health reporting.",
        "2. Ranking and editorial checks reject repeats, routine noise, and unsupported claims.",
        "3. The episode manifest binds every selected story to its evidence and becomes the source of truth.",
        "4. Narration or reviewed browser audio is validated before an immutable release is created.",
        "5. Publication is confirmed only after the feed serves the exact expected episode and media bytes.",
        "",
        "A healthy thin-news day can intentionally skip publication. Failures before candidate publication leave "
        "the existing subscriber feed untouched. A delivery failure after deployment can leave an unconfirmed "
        "candidate visible; it must be recovered without replacing its audio or advancing novelty state.",
        "",
        "```mermaid",
        "flowchart TD",
        '    schedule["Daily schedule or manual run"] --> prepare["Collect and select public evidence"]',
        '    config["topics/topics.yaml"] --> prepare',
        '    weekly["Weekly YouTube digest"] --> prepare',
        '    prepare -->|Healthy thin-news day| skip["Record skip; keep existing feed"]',
        '    prepare -->|Selected stories| script["Episode manifest and narration"]',
        '    script -->|Text to speech| validate["Validate media, duration and checksum"]',
        '    reviewed["Operator-reviewed Notebook audio or special"] --> validate',
        '    validate --> release["GitHub Release: immutable MP3 and manifest"]',
        '    release --> candidate["Verify release; commit candidate RSS, README and manifest"]',
        '    candidate --> pages["Deploy RSS and artwork to GitHub Pages"]',
        '    pages -->|Discover episodes| clients["Apple Podcasts and other RSS apps"]',
        '    release -->|Stream or download MP3| clients',
        '    clients --> carplay["CarPlay through the iPhone app"]',
        '    pages --> delivery["Check exact public GUID, audio bytes and artwork"]',
        '    release --> delivery',
        '    delivery --> confirmed["Confirm receipt and advance novelty state"]',
        "```",
        "",
        "Approved manual imports join the same serialized publisher; issue intake and unpublished previews "
        "do not publish episodes. The diagram shows the successful publication path and intentional skip; "
        "validation failures stop the run. HTTP delivery checks do not certify iPhone or CarPlay playback.",
        "",
        "## When and where it publishes",
        "",
        "| Process | Trigger / target time | Result |",
        "| --- | --- | --- |",
        "| [Daily publisher](.github/workflows/update-radar.yml) | Daily **10:17 UTC** "
        "(06:17 EDT / 05:17 EST), or manual | Evaluates new evidence; publishes only when gates pass. |",
        "| [Reviewed imports and specials](docs/OPERATIONS.md#publishing-approved-notebook-audio) "
        "| Manual, after review and authorization | Uses the daily publisher with a `reviewed_episode` release tag. |",
        "| [Pages recovery](.github/workflows/pages.yml) | Relevant pushes to `main`, or manual "
        "| Redeploys the existing feed and artwork; does not generate audio. |",
        "| [Feed health](.github/workflows/feed-health.yml) | Daily **12:47 UTC** "
        "(08:47 EDT / 07:47 EST), or manual | Checks delivery and a 25-hour freshness budget; "
        "accepts verified intentional skips and reports failures in an issue. |",
        "| [YouTube discovery](.github/workflows/youtube-trends.yml) | Sunday **11:23 UTC** "
        "(07:23 EDT / 06:23 EST), or manual | Updates an input digest, not a standalone podcast episode. |",
        "",
        "These are GitHub Actions schedule targets, not guaranteed release times. Publication requires "
        "preparation, release upload, Pages deployment, and subscriber-facing verification. Apple Podcasts "
        "refreshes and downloads independently; there is no scheduled push directly to Apple or CarPlay.",
        "",
        f"- **Discovery:** [RSS feed]({feed_url}) and show artwork on GitHub Pages. "
        "The Pages site does not host episode MP3s or the rendered README.",
        "- **Audio:** [GitHub Releases](https://github.com/johnsirmon/daily-ai-docs/releases), "
        "using a permanent, unique enclosure URL for each episode. Released bytes and GUIDs are never replaced.",
        "- **Written brief:** this README on the repository's `main` branch, generated from the episode manifest.",
        "- **Audit trail:** [`data/episodes`](data/episodes), [`data/receipts`](data/receipts), "
        "[`data/runs/latest.json`](data/runs/latest.json), and [`data/state.json`](data/state.json). "
        "The manifest/RSS timestamp is assigned before delivery; `confirmed_at` records successful verification.",
        "",
        "Daily publishing, standalone Pages deployment, and weekly digest writes share the non-cancelling "
        "`podcast-publisher` lock. The daily job deploys Pages inline rather than waiting on another locked job. "
        "See [publishing review and optimization priorities](docs/OPERATIONS.md#publishing-review-and-optimization-priorities).",
        "",
        "## Try the Notebook browser pilot",
        "",
        "1. Sign in to Gemini Notebook and create a dedicated notebook for the pilot.",
        "2. Add only the selected public primary-source URLs; include full methods and limitations for research.",
        "3. Configure an English Deep Dive targeting 5–8 minutes with concrete changes, implications, and caveats.",
        "4. Generate once, download once, and complete the native Save dialog manually if the browser cannot.",
        "5. Preserve the original file, fully decode it, measure its duration, and record its size and SHA-256.",
        "6. Review the transcript and consequential spoken claims against the imported primary sources.",
        "",
        "The pilot uses the signed-in account's existing allowance. It does not authorize a paid upgrade, "
        "cookie export, unattended browser automation, or publication. Approved recordings use the separate "
        "[reviewed-audio handoff](docs/OPERATIONS.md#publishing-approved-notebook-audio).",
        "",
        *([
            "### Editorial correction",
            "",
            manifest.generation["editing"]["correction_text"],
            "",
        ] if manifest.schema_version in {3, 4} and "editing" in manifest.generation else []),
        "## Today's signal",
        "",
    ]
    if manifest.schema_version == 4:
        request = manifest.generation["request"]
        lines[0] = f"# Daily AI Developer Brief — Special: {request['topic']}"
        lines += [
            f"Long-form special for {request['audience']}.",
            f"Evidence window: {request['lookback_days']} days ending {request['cutoff']}.",
            f"Audio provider: {manifest.generation['provider']}; transcript/source reviewed, not Gemini API verification.",
            "",
        ]
    if not manifest.stories:
        failed = [status for status in manifest.source_health.values() if not status.startswith("ok:")]
        quiet_message = (
            "No item established enough developer utility for an episode today. Coverage was incomplete; "
            "review the source-health details below."
            if failed
            else "No item established a specific action, decision, risk, or reusable lesson today. "
                 "This is a healthy quiet day, not a source outage."
        )
        lines += [
            quiet_message,
            "",
        ]
    labels = {}
    for event in manifest.source_events:
        label = source_display_label(event)
        if label:
            labels[event.url] = label
    for story in manifest.stories:
        lines += [
            f"### {story.headline}",
            "",
            f"**What to know:** {story.what_changed}",
            "",
            f"**What changes for developers:** {story.why_it_matters}",
            "",
            f"**Recommendation:** {story.action.upper()} — {story.rationale}",
            "",
            "Sources: " + ", ".join(
                f"[{index + 1}]({url})" + (f" — {labels[url]}" if url in labels else "")
                for index, url in enumerate(story.source_urls)
            ),
            "",
        ]
        if story.kind == "research":
            review = story.editorial["paper_review"]
            lines += [
                f"**Research evidence:** {review['evidence_status']}",
                "",
                f"**Question:** {review['question']}",
                "",
                f"**Method:** {review['method']}",
                "",
                f"**Result:** {review['result']}",
                "",
                f"**Limitations:** {review['limitations']}",
                "",
                f"**Experiment to try:** {review['takeaway']}",
                "",
            ]
    if manifest.noise_notes:
        lines += ["## High noise / low signal", ""]
        lines.extend(f"- {note}" for note in manifest.noise_notes)
        lines.append("")
    lines += [
        "## Editorial contract",
        "",
        *([
            "- This edition uses user-authorized Gemini Notebook web audio, a local-ASR transcript, and an assistant transcript/source comparison; it is not independently verified Gemini API generation.",
            "",
        ] if manifest.schema_version == 3 else []),
        *([
            "- An Edge-TTS editorial correction precedes the retained Notebook conversation; the manifest records both component hashes and the exact correction text.",
            "",
        ] if manifest.schema_version in {3, 4} and "editing" in manifest.generation else []),
        "- Scheduled daily at **10:17 UTC**; GitHub Actions timing is best-effort.",
        "- One to three useful stories, at most one per canonical product and one research item; thin-news runs skip instead of padding.",
        "- Opt-in grounded editorial mode groups meaningful changes into 5–8-minute briefs without changing the feed on thin-news days.",
        "- Grounded mode can include one reviewed recent-paper takeaway, with its method, limitations, and practical experiment; it does not repeat papers as filler.",
        "- Product-change claims require public primary evidence.",
        (
            "- This edition preserves a conversational format; `ACT`, `WATCH`, or `SKIP` recommendations appear in the written story notes, not as required spoken endings."
            if manifest.schema_version in {2, 3, 4}
            or manifest.generation.get("narration_style") in {"explanatory-v1", "explanatory-v2"}
            else "- Every story ends with an `ACT`, `WATCH`, or `SKIP` recommendation."
        ),
        "- Routine patches, repeated announcements, unsupported adoption claims, and engagement-only rankings are filtered out.",
        "- At most one transcript-backed YouTube learning pick may appear; it never replaces vendor evidence.",
        "",
        "## Tracked areas",
        "",
        "The active `daily.sources` configuration in [`topics/topics.yaml`](topics/topics.yaml) monitors public releases and feeds for GitHub Copilot, VS Code, OpenAI Codex, Claude Code, Gemini CLI, Hermes Agent, MCP, and Agent Skills. Evaluation and observability are covered through bounded YouTube learning discovery rather than dedicated primary-source collectors.",
        "",
        "## Source health",
        "",
        *[f"- `{name}`: {status}" for name, status in sorted(manifest.source_health.items())],
        "",
        "Each edition manifest distinguishes healthy no-news results from source outages.",
        "",
        "## Publication flow",
        "",
        "`collect → select → manifest → narrate/audio → validate → publish → verify delivery → confirm`",
        "",
        "The versioned episode manifest is the source of truth for narration, show notes, and this README. Preparation and failed delivery do not advance novelty state.",
        "All intentional skips have durable run receipts. Monitoring still verifies the last confirmed feed, audio, and artwork and rejects failed or stale evaluations.",
        "",
        "## Weekly YouTube signal",
        "",
        "The Sunday **11:23 UTC** workflow runs four focused searches and retains up to five videos with short transcript-derived takeaways. Full transcripts are never committed, and at most one deduplicated learning pick may enter a daily edition.",
        "",
        "## Development",
        "",
        "```bash",
        "# Reproducible test suite",
        "uv run --with-requirements requirements.lock pytest -q",
        "",
        "# Network-free manifest preparation; writes only under .cache/",
        "uv run --with-requirements requirements.lock \\",
        "  python -m pipeline.daily prepare --dry-run --no-audio",
        "```",
        "",
        "Preparation does not publish or modify the subscriber feed. See [operations and setup](docs/OPERATIONS.md) for credentials, deployment, recovery, and manual commands.",
        "",
    ]
    return "\n".join(lines)


def write_manifest_readme(manifest, path: str = "README.md", feed_url: str | None = None) -> Path:
    output = Path(path)
    output.write_text(render_manifest_readme(manifest, feed_url=feed_url), encoding="utf-8")
    return output
