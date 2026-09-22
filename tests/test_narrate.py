"""Tests for pipeline/narrate.py."""

import pipeline.narrate as _narrate_mod
from pipeline.narrate import readme_to_narration, _strip_markdown, _normalise_sentence
from pipeline.schema import EpisodeManifest, SourceEvent, Story


_SAMPLE_README = """\
# AI Skills Radar — 2026-03-01

_Updated: 2026-03-01T00:00:00Z | Covers last 14 days_

> Auto-generated. To refresh, go to **Actions → Update AI Skills Radar → Run workflow**.

## Topics

- [MCP Ecosystem](#mcp)
- [Azure AI](#azure-ai)

---

## MCP Ecosystem

> **Why it matters:** MCP is reshaping how AI tools connect.
>
> **What to learn:** Build your first MCP server.

### 🌱 New & Rising Repos

| Repo | Stars | Forks | Issues | Language | Trend |
|------|-------|-------|--------|----------|-------|
| [org/repo](https://github.com) | ⭐ 500 | 42 | 7 | Python | 📈 rising |

### 🚀 Recent Releases

| Repo | Version | Date | Highlights |
|------|---------|------|------------|
| [org/repo](https://github.com) | `v2.0.1` | 2026-03-01 | Adds better plugin support |

---

## Azure AI

> **Why it matters:** Azure AI Foundry is centralising AI deployments.
>
> **What to learn:** Prompt flow and evaluation pipelines.

---

_[Pipeline source](.github/workflows/update-radar.yml) · [Config](topics/topics.yaml)_
"""

# README with a repo deep-dive section to test slash-pronunciation and introductions.
_DEEPDIVE_README = """\
# AI Skills Radar — 2026-03-01

## MCP Ecosystem

### 🔍 Repo Deep Dives

#### `microsoft/semantic-kernel`

_⭐ 22,000 · Python · 1,234 forks_

This is a great framework for orchestrating AI.

"""


def _reset_counters():
    """Reset rotation counters so each test starts from index 0."""
    _narrate_mod._topic_idx = 0
    _narrate_mod._repo_idx = 0


def test_legacy_manifest_narration_remains_byte_for_byte_unchanged():
    event = SourceEvent(
        "event-1", "announcement", "Tool update", "https://example.com/tool", "Tool", "Agents",
        "2026-09-17T10:00:00Z", "2026-09-17T11:00:00Z", "Adds command previews.",
    )
    story = Story(
        "story-1", ["event-1"], "Tool update", "Adds command previews.", "Inspect commands.",
        "watch", "Try the preview.", [event.url], {"total": 80},
    )
    manifest = EpisodeManifest(
        1, "daily-1", "2026-09-17T12:00:00Z", "draft", {"primary": "ok:1"},
        [event], [story], [], "Draft placeholder.", "Source notes.", {}, {},
    )
    assert _narrate_mod.manifest_to_narration(manifest) == (
        "This is your Daily AI Developer Brief for 2026-09-17. Today's lead is Tool update. "
        "I filtered the rest down to 1 update worth your attention.\n\n"
        "Here is the lead: Tool update. Adds command previews. Inspect commands. "
        "The call is watch. Try the preview.\n\n"
        "That is the useful signal for today. Source links and exact versions are in the episode notes. "
        "Keep building, and I will be back tomorrow."
    )


def test_narration_contains_date_heading():
    _reset_counters()
    result = readme_to_narration(_SAMPLE_README)
    assert "AI Skills Radar" in result
    assert "2026-03-01" in result


def test_narration_contains_topic_headings():
    _reset_counters()
    result = readme_to_narration(_SAMPLE_README)
    assert "MCP Ecosystem" in result
    assert "Azure AI" in result


def test_narration_topic_transition_is_conversational():
    _reset_counters()
    result = readme_to_narration(_SAMPLE_README)
    # Should NOT use the old mechanical label.
    assert "Next topic:" not in result
    # Should use one of the conversational rotation phrases.
    assert any(
        phrase in result
        for phrase in ("Now let's look at", "Moving on to", "Let's turn to")
    )


def test_narration_contains_blurbs_without_labels():
    _reset_counters()
    result = readme_to_narration(_SAMPLE_README)
    # Blurb content should be present.
    assert "MCP is reshaping how AI tools connect" in result
    assert "Build your first MCP server" in result
    assert "Azure AI Foundry is centralising AI deployments" in result
    # Written-word labels should NOT appear in the spoken output.
    assert "Why it matters:" not in result
    assert "What to learn:" not in result


def test_narration_blurb_uses_spoken_bridge():
    _reset_counters()
    result = readme_to_narration(_SAMPLE_README)
    # Conversational bridges should be present.
    assert "Here's why this matters" in result
    assert "Here's what to focus on learning" in result


def test_narration_includes_repo_context_from_table():
    _reset_counters()
    result = readme_to_narration(_SAMPLE_README)
    assert "repo by org" in result.lower()
    assert "500 stars" in result
    assert "42 forks" in result
    assert "7 open issues" in result
    assert "primarily Python" in result
    assert "momentum is rising" in result


def test_narration_includes_release_context_from_table():
    _reset_counters()
    result = readme_to_narration(_SAMPLE_README)
    assert "Org/repo shipped v2.0.1 on 2026-03-01" in result
    assert "Adds better plugin support" in result


def test_narration_omits_toc():
    _reset_counters()
    result = readme_to_narration(_SAMPLE_README)
    assert "- [MCP Ecosystem]" not in result


def test_narration_omits_footer():
    _reset_counters()
    result = readme_to_narration(_SAMPLE_README)
    assert "Pipeline source" not in result
    assert "update-radar.yml" not in result


def test_narration_omits_auto_generated_line():
    _reset_counters()
    result = readme_to_narration(_SAMPLE_README)
    assert "Auto-generated" not in result


def test_narration_repo_introduction_no_slash():
    _reset_counters()
    result = readme_to_narration(_DEEPDIVE_README)
    # Repo announced without a slash.
    assert "slash" not in result.lower()
    assert "/" not in result or "Here's" in result  # bridge text may contain apostrophe
    # Should use "by" to separate org and repo.
    assert "semantic-kernel by microsoft" in result.lower()


def test_narration_repo_introduction_is_conversational():
    _reset_counters()
    result = readme_to_narration(_DEEPDIVE_README)
    assert "Repository:" not in result
    assert any(
        phrase in result
        for phrase in ("Let's dive into", "Up next is")
    )


def test_narration_strips_markdown_links():
    result = _strip_markdown("[some link](https://example.com)")
    assert "some link" in result
    assert "https://example.com" not in result


def test_narration_strips_bold():
    result = _strip_markdown("**Why it matters:** Something important.")
    assert "**" not in result
    assert "Why it matters:" in result


def test_normalise_sentence_capitalises():
    assert _normalise_sentence("hello world") == "Hello world."


def test_normalise_sentence_adds_period():
    assert _normalise_sentence("already good") == "Already good."


def test_normalise_sentence_preserves_existing_punctuation():
    assert _normalise_sentence("Is this right?") == "Is this right?"
    assert _normalise_sentence("Yes!") == "Yes!"


def test_empty_readme():
    _reset_counters()
    result = readme_to_narration("")
    assert result == ""


# ── Cold open / closing ──────────────────────────────────────────────────────

def test_cold_open_prepended_when_report_provided():
    _reset_counters()
    report = {
        "week_story": "Big things happened.",
        "narrative_hook": "This week in AI, everything changed.",
        "topic_insights": {},
    }
    result = readme_to_narration(_SAMPLE_README, research_report=report)
    assert result.startswith("This week in AI, everything changed.")


def test_closing_appended_when_report_provided():
    _reset_counters()
    report = {"week_story": "", "narrative_hook": "", "topic_insights": {}}
    result = readme_to_narration(_SAMPLE_README, research_report=report)
    assert "AI Skills Radar for the week" in result


def test_no_cold_open_without_report():
    _reset_counters()
    result = readme_to_narration(_SAMPLE_README)
    assert "This week in AI" not in result
    assert "AI Skills Radar for the week" not in result


def test_cold_open_fallback_when_hook_empty():
    from pipeline.narrate import build_cold_open
    result = build_cold_open({"narrative_hook": "", "week_story": "", "topic_insights": {}})
    assert "This week" in result


def test_build_closing_is_non_empty():
    from pipeline.narrate import build_closing
    closing = build_closing()
    assert len(closing) > 20
    assert "week" in closing.lower()


def _daily_manifest(*, marked=False, evidence=None, channel="stable", source_type="github_release",
                    narration_style=None):
    from pipeline.rank import event_to_story
    from pipeline.schema import EpisodeManifest, SourceEvent, Story

    source = SourceEvent(
        "example", source_type, "Tool approval update", "https://example.com/change",
        "Tool", "Coding", "2026-09-19T10:00:00Z", "2026-09-19T11:00:00Z",
        evidence or "Tool adds a command approval preview. Existing approvals remain required.",
        channel=channel,
    )
    story = event_to_story(source)
    if not marked:
        story = Story(
            story.story_id, story.event_ids, story.headline, story.what_changed,
            "This is relevant to developers tracking Coding.", story.action,
            "Read the primary source and assess applicability before changing your workflow.",
            story.source_urls, story.scores,
        )
    return EpisodeManifest(
        1, "daily-example", "2026-09-19T12:00:00Z", "draft", {"source": "ok:1"},
        [source], [story], [], "pending", "Source notes.",
        {"narration_style": narration_style or "explanatory-v1"} if marked else {}, {},
    )


def test_unmarked_daily_narration_remains_byte_exact():
    from pipeline.narrate import manifest_to_narration
    from pipeline.schema import EpisodeManifest

    manifest = _daily_manifest()
    expected = (
        "This is your Daily AI Developer Brief for 2026-09-19. "
        "Today's lead is Tool approval update. I filtered the rest down to 1 update worth your attention.\n\n"
        "Here is the lead: Tool approval update. Tool adds a command approval preview. "
        "Existing approvals remain required. This is relevant to developers tracking Coding. "
        "The call is watch. Read the primary source and assess applicability before changing your workflow.\n\n"
        "That is the useful signal for today. Source links and exact versions are in the episode notes. "
        "Keep building, and I will be back tomorrow."
    )
    assert manifest_to_narration(manifest) == expected
    manifest.narration = expected
    original = manifest.to_dict()
    assert EpisodeManifest.from_dict(original).to_dict() == original
    assert "narration_style" not in original["generation"]


def test_marked_daily_narration_omits_generated_filler_but_keeps_late_security_conditions():
    from pipeline.narrate import manifest_to_narration
    from pipeline.schema import EpisodeManifest

    evidence = (
        "Tool fixes a security vulnerability. Approval previews remain available. "
        "Remote execution still requires approval. Only versions 1.2.0 through 1.2.3 are affected. "
        "Version 1.2.4 contains the fix; installations with remote execution disabled are unaffected."
    )
    manifest = _daily_manifest(marked=True, evidence=evidence)
    assert "[Excerpt;" in manifest.stories[0].what_changed
    text = manifest_to_narration(manifest)
    assert text.count("Tool approval update") == 1
    assert evidence in text
    for unwanted in ("Today's lead", "Here is the lead", "The call is", "This is relevant",
                     "assess applicability", "[Excerpt;", "see source for full details"):
        assert unwanted not in text
    manifest.narration = text
    assert EpisodeManifest.from_dict(manifest.to_dict()).narration == text


def test_marked_daily_narration_preserves_prerelease_and_learning_qualifications():
    from pipeline.narrate import manifest_to_narration

    manifest = _daily_manifest(marked=True, channel="prerelease",
                               evidence="Tool 2.0.0-rc1 adds previews for opted-in users only.")
    text = manifest_to_narration(manifest)
    assert "not a stable release" in text
    assert "Tool 2.0.0-rc1" in text and "opted-in users only" in text
    learning = manifest_to_narration(_daily_manifest(marked=True, source_type="youtube_video"))
    assert "not verified product-change evidence" in learning


def test_prospective_daily_narration_discloses_ai_and_scopes_optional_outage():
    from pipeline.narrate import manifest_to_narration

    manifest = _daily_manifest(marked=True, narration_style="explanatory-v2")
    manifest.source_health = {"github:tool": "ok:1", "youtube:weekly": "error:stale"}
    text = manifest_to_narration(manifest)
    assert "Production note: This episode uses AI-generated narration." in text
    assert "Supplementary learning coverage was unavailable" in text
    assert "edition is incomplete" not in text


def test_prospective_daily_narration_identifies_primary_outage():
    from pipeline.narrate import manifest_to_narration

    manifest = _daily_manifest(marked=True, narration_style="explanatory-v2")
    manifest.source_health = {"github:tool": "error:timeout", "youtube:weekly": "ok:1"}
    text = manifest_to_narration(manifest)
    assert "Primary-source coverage note" in text
    assert "edition is incomplete" in text


def test_presentation_distinguishes_marked_and_unmarked_daily_narration():
    from pipeline.render import render_manifest_readme

    assert "Every story ends with" in render_manifest_readme(_daily_manifest())
    marked = render_manifest_readme(_daily_manifest(marked=True))
    assert "not as required spoken endings" in marked
    assert "Every story ends with" not in marked


def test_marked_daily_narration_fails_instead_of_truncating_over_budget_evidence():
    import pytest
    from dataclasses import replace
    from pipeline.narrate import manifest_to_narration
    from pipeline.rank import event_to_story

    manifest = _daily_manifest(marked=True, evidence="Tool adds approval previews. " * 120)
    manifest.source_events = [
        replace(manifest.source_events[0], event_id=f"e{index}") for index in range(7)
    ]
    manifest.stories = [event_to_story(source) for source in manifest.source_events]
    with pytest.raises(ValueError, match="budget"):
        manifest_to_narration(manifest)
