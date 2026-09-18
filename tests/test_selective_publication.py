import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from pipeline.daily import _print_github_output, collect_events, prepare
from pipeline.publish import PublicationError
from pipeline.rank import group_editorial_stories, score_event, select_editorial_events
from pipeline.run_health import RUN_PATH, skip_candidate
from pipeline.schema import EpisodeManifest, SourceEvent
from pipeline.source_health import primary_source_health

NOW = datetime(2026, 9, 17, 15, tzinfo=timezone.utc)


def event(identity="release", *, evidence="Adds support for typed tool arguments in coding sessions.",
          product="Tool", channel="stable"):
    return SourceEvent(
        identity, "github_release", f"{product} {identity}", f"https://example.com/{identity}",
        product, "AI coding agents", NOW.isoformat(), NOW.isoformat(), evidence,
        channel=channel, metadata={"priority": 20, "version": identity},
    )


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def setup_config(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AI_EDITORIAL", "required")
    path = tmp_path / "topics.yaml"
    path.write_text("daily:\n  minimum_source_health: 0.6\n  editorial:\n    enabled: false\n")
    (tmp_path / "podcast.xml").write_text("last-good-feed")
    return path


def test_title_only_alpha_flood_is_ineligible_even_with_momentum():
    alphas = [event(f"alpha-{index}", evidence=f"Release 0.155.0-alpha.{index}", channel="prerelease")
              for index in range(5)]
    assert score_event(alphas[0])["total"] == 84
    alphas = [replace(item, metadata={**item.metadata, "star_velocity": 10000}) for item in alphas]
    selected, reasons = select_editorial_events(alphas, now=NOW)
    assert not selected and reasons


@pytest.mark.parametrize("mode,papers_enabled", [("off", False), ("required", True)])
def test_enrichment_is_independent_while_papers_require_editorial(monkeypatch, mode, papers_enabled):
    monkeypatch.setenv("AI_EDITORIAL", mode)
    captured = []
    source = {"repo": "example/tool", "enrichment": {"enabled": True, "allowed_hosts": ["example.com"]}}
    config = {"daily": {"sources": {"github_releases": [source], "papers": {"enabled": True}}}}
    def github(items, **kwargs):
        captured.extend(items)
        return [], {"github:example/tool": "ok:0"}
    def papers(options, **kwargs):
        assert papers_enabled and options["enabled"]
        return [], {"research:arxiv": "ok:0", **{
            f"research:arxiv:paper-{index}": "rejected:outside_first_publication_window"
            for index in range(10)
        }}
    monkeypatch.setattr("pipeline.daily.collect_github_releases", github)
    monkeypatch.setattr("pipeline.daily.collect_official_feeds", lambda *args, **kwargs: ([], {}))
    monkeypatch.setattr("pipeline.daily.collect_youtube_digest", lambda *args, **kwargs: ([], {}))
    monkeypatch.setattr("pipeline.daily.collect_research_papers", papers)
    events, health = collect_events(config, dry_run=False, now=NOW)
    assert not events and health["github:example/tool"] == "ok:0"
    assert captured[0]["enrichment"]["enabled"] is True
    assert source["enrichment"]["enabled"] is True


def test_production_paper_configuration_builds_a_valid_bounded_query(monkeypatch):
    from pipeline.sources.papers import collect_research_papers
    from urllib.parse import parse_qs, urlsplit

    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / "topics/topics.yaml").read_text())["daily"]["sources"]["papers"]
    def empty_feed(url, **kwargs):
        query = parse_qs(urlsplit(url).query)
        assert 'all:"coding agents"' in query["search_query"][0]
        assert query["max_results"] == ["5"]
        return '<feed xmlns="http://www.w3.org/2005/Atom"></feed>', url, "application/atom+xml"
    monkeypatch.setattr("pipeline.sources.papers.fetch_public", empty_feed)
    events, health = collect_research_papers(config, now=NOW)
    assert not events and health["research:arxiv"] == "ok:0"


def test_optional_youtube_health_cannot_inflate_primary_source_quorum():
    health = {
        "github:a": "ok:0", "github:b": "error:timeout",
        "youtube:weekly-digest": "ok:1",
        "feed:x:detail:item": "error:timeout",
        "research:arxiv:paper": "rejected:missing",
    }
    assert primary_source_health(health) == {
        "github:a": "ok:0", "github:b": "error:timeout",
    }


@pytest.mark.parametrize("evidence", [
    "https://code.visualstudio.com/updates/v1_138",
    "What's changed - Bug fixes and reliability improvements",
    "Published 1.2.3.",
])
def test_generic_updates_are_not_substantive(evidence):
    assert not select_editorial_events([event(evidence=evidence)], now=NOW)[0]


def test_preview_warning_and_stable_milestone_remain_eligible():
    preview = event("preview", evidence="Security patch fixes a vulnerability in tool execution.",
                    channel="prerelease")
    stable = event("stable", evidence="Adds support for typed tool arguments in stable sessions.")
    selected, _ = select_editorial_events([preview, stable], now=NOW)
    assert len(selected) == 2
    grouped = group_editorial_stories(selected)
    assert len(grouped) == 1 and set(grouped[0].event_ids) == {"preview", "stable"}
    assert select_editorial_events([stable], ["preview"], now=NOW)[0] == [stable]


def test_substantive_fix_is_not_vetoed_by_documentation_sentence():
    item = event(evidence="Fixed a crash when the tool host disconnects. Documentation explains the recovery steps.")
    assert select_editorial_events([item], now=NOW)[0] == [item]


def test_rejected_unpublished_event_can_be_reconsidered():
    item = event()
    assert select_editorial_events([item], now=NOW)[0] == [item]
    assert select_editorial_events([item], now=NOW + timedelta(hours=1))[0] == [item]
    assert not select_editorial_events([item], [item.event_id], now=NOW)[0]


def test_different_tag_does_not_repeat_identical_published_claim():
    item = event("new-tag")
    previous = [{"canonical_event_id": "old-tag", "product": item.product, "channel": "stable",
                 "published_at": (NOW - timedelta(days=1)).isoformat(),
                 "normalized_evidence": item.evidence.casefold()}]
    assert not select_editorial_events([item], published_events=previous, now=NOW)[0]
    previous[0]["channel"] = "prerelease"
    assert select_editorial_events([item], published_events=previous, now=NOW)[0] == [item]


def test_same_url_revision_requires_new_evidence_and_source_revision_date():
    item = event()
    previous = [{"canonical_event_id": item.event_id, "product": item.product, "channel": "stable",
                 "published_at": (NOW - timedelta(days=1)).isoformat(),
                 "normalized_evidence": "adds support for an earlier feature."}]
    assert not select_editorial_events([item], [item.event_id], published_events=previous, now=NOW)[0]
    revised = replace(item, metadata={**item.metadata, "updated_at": NOW.isoformat()})
    selected, _ = select_editorial_events([revised], [item.event_id], published_events=previous, now=NOW)
    assert len(selected) == 1 and ":rev:" in selected[0].event_id
    assert selected[0].metadata["canonical_event_id"] == item.event_id
    assert not select_editorial_events([revised], [item.event_id, selected[0].event_id],
                                       published_events=previous, now=NOW)[0]


def test_research_is_bounded_reviewable_and_not_a_quiet_day_fallback():
    paper = replace(event("paper", product="Research"), source_type="research_paper", metadata={
        "priority": 20, "paper_id": "2609.12345", "version": "v1",
        "first_published_at": NOW.isoformat(), "updated_at": NOW.isoformat(),
        "full_text_available": True, "full_text": "Methods and results with explicit limitations.",
    })
    assert not select_editorial_events([paper], now=NOW)[0]
    assert paper in select_editorial_events([event(), paper], now=NOW)[0]
    assert paper not in select_editorial_events([event(), paper], covered_paper_ids=["2609.12345"], now=NOW)[0]
    stale = replace(paper, metadata={**paper.metadata, "first_published_at": (NOW - timedelta(days=31)).isoformat()})
    assert stale not in select_editorial_events([event(), stale], now=NOW)[0]
    other = replace(paper, event_id="another-paper", metadata={**paper.metadata, "paper_id": "2609.56789"})
    assert other in select_editorial_events([event(), paper, other], covered_paper_ids=["2609.12345"], now=NOW)[0]


def test_thin_run_skips_model_audio_feed_and_published_state(monkeypatch, tmp_path, capsys):
    config = setup_config(monkeypatch, tmp_path)
    monkeypatch.setattr("pipeline.daily.collect_events", lambda *args, **kwargs: (
        [event(evidence="Release 0.155.0-alpha.16", channel="prerelease")], {"source": "ok:1"},
    ))
    def forbidden(*args, **kwargs):
        raise AssertionError("thin run must not generate")
    monkeypatch.setattr("pipeline.daily.refine_editorial", forbidden)
    monkeypatch.setattr("pipeline.daily.write_audio", forbidden)
    result = prepare(config, now=NOW)
    assert result["outcome"] == "skipped" and not result["audio_path"]
    assert Path("podcast.xml").read_text() == "last-good-feed"
    assert not Path("data/state.json").exists()
    assert json.loads(RUN_PATH.read_text())["status"] == "skipped"
    _print_github_output(result)
    assert "outcome=skipped" in capsys.readouterr().out


def test_deterministic_thin_run_skips_synthesis_audio_and_state(monkeypatch, tmp_path):
    config = setup_config(monkeypatch, tmp_path)
    monkeypatch.setenv("AI_EDITORIAL", "off")
    monkeypatch.setattr("pipeline.daily.collect_events", lambda *args, **kwargs: (
        [event(evidence="Release 0.155.0-alpha.16", channel="prerelease")], {"source": "ok:1"},
    ))

    def forbidden(*args, **kwargs):
        raise AssertionError("thin deterministic run must not generate")

    monkeypatch.setattr("pipeline.daily.refine_stories", forbidden)
    monkeypatch.setattr("pipeline.daily.write_audio", forbidden)
    result = prepare(config, now=NOW)
    assert result["outcome"] == "skipped" and not result["audio_path"]
    assert Path("podcast.xml").read_text() == "last-good-feed"
    assert not Path("data/state.json").exists()
    assert json.loads(RUN_PATH.read_text())["status"] == "skipped"


def test_model_failure_is_not_a_healthy_skip_or_fallback(monkeypatch, tmp_path):
    config = setup_config(monkeypatch, tmp_path)
    monkeypatch.setattr("pipeline.daily.collect_events", lambda *args, **kwargs: ([event()], {"source": "ok:1"}))
    def quota_failure(*args, **kwargs):
        raise RuntimeError("quota exhausted")
    monkeypatch.setattr("pipeline.daily.refine_editorial", quota_failure)
    with pytest.raises(RuntimeError, match="quota"):
        prepare(config, now=NOW)
    assert Path("podcast.xml").read_text() == "last-good-feed"
    assert not Path("data/state.json").exists()
    assert json.loads(RUN_PATH.read_text())["status"] == "failed"


@pytest.mark.parametrize("audio_valid", [True, False])
def test_grounded_prepare_wires_verified_script_and_measured_budget(monkeypatch, tmp_path, audio_valid):
    from pipeline.audio import AudioValidationError

    config = setup_config(monkeypatch, tmp_path)
    config.write_text("daily:\n  editorial:\n    minimum_words: 100\n    maximum_words: 300\n")
    evidence = (
        "This release adds support for explicit tool permissions in shared coding sessions. "
        "The permission check runs before a tool starts, so a denied request cannot launch the tool. "
        "Teams can inspect the requested operation before deciding whether to grant access. "
        "The release does not change the existing permission settings for projects already configured. "
        "If you maintain a shared development environment, compare the new checks with your current policy. "
        "Try a permitted operation and a denied operation in an isolated workspace before changing defaults. "
        "Keep the existing configuration available so that you can compare the results and restore the prior policy. "
        "The release notes describe the supported settings and the expected denial message."
    )
    source = event(evidence=evidence)
    spoken = ". ".join(reversed(evidence.rstrip(".").split(". "))) + "."
    monkeypatch.setattr("pipeline.daily.collect_events", lambda *args, **kwargs: ([source], {"source": "ok:1"}))

    def verified(events, fallback, history, *, config):
        assert config["target_min_words"] == 100 and config["target_max_words"] == 300
        story = replace(
            fallback[0], what_changed=evidence,
            why_it_matters="Teams can inspect the requested operation before deciding whether to grant access.",
            rationale="Try a permitted operation and a denied operation in an isolated workspace before changing defaults.",
            editorial={"spoken_text": spoken, "claims": [
                {"text": evidence, "event_id": source.event_id, "quote": evidence},
            ]},
        )
        return [story], {"provider": "gemini", "model": "gemini-3.8-flash", "calls": 2,
                         "editorial_version": 1, "verified": True,
                         "opening": "Here is the change to examine in your development workflow.",
                         "closing": "The source and exact settings are in the episode notes."}

    monkeypatch.setattr("pipeline.daily.refine_editorial", verified)
    monkeypatch.setattr("pipeline.daily.write_audio", lambda *args, **kwargs: ".cache/daily-ai-brief.mp3")

    def measured(path, *, min_duration_secs, max_duration_secs, expected_word_count):
        assert (min_duration_secs, max_duration_secs) == (300, 480)
        assert expected_word_count >= 100
        if not audio_valid:
            raise AudioValidationError("duration outside 300-480s")
        return {"size_bytes": 12000, "duration_secs": 400, "sha256": "b" * 64,
                "codec": "mp3", "sample_rate": 24000, "channels": 1}

    monkeypatch.setattr("pipeline.daily.analyze_audio", measured)
    if audio_valid:
        result = prepare(config, now=NOW)
        manifest = EpisodeManifest.from_dict(json.loads(Path(result["manifest_path"]).read_text()))
        assert result["outcome"] == "publish"
        assert manifest.schema_version == 2 and manifest.status == "ready"
        assert manifest.generation["verified"] is True and spoken in manifest.narration
    else:
        with pytest.raises(AudioValidationError, match="300-480"):
            prepare(config, now=NOW)
        assert json.loads(RUN_PATH.read_text())["status"] == "failed"
    assert Path("podcast.xml").read_text() == "last-good-feed"
    assert not Path("data/state.json").exists()


def confirmed_skip(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    stamp = (NOW - timedelta(days=4)).isoformat()
    manifest = EpisodeManifest(
        1, "daily-confirmed", stamp, "published", {"source": "ok:1"}, [], [], [],
        "An older confirmed episode, retained without changing its audio.", "Source notes.",
        {"edition": "quiet"}, {"url": "https://example.com/audio.mp3", "size_bytes": 12345,
                              "duration_secs": 60, "sha256": "a" * 64},
    )
    save("data/state.json", {"schema_version": 1, "seen_event_ids": [], "last_episode_id": manifest.episode_id,
                            "last_publication": stamp})
    save(f"data/episodes/{manifest.episode_id}.json", manifest.to_dict())
    save(f"data/receipts/{manifest.episode_id}.json",
         {"episode_id": manifest.episode_id, "audio_sha256": manifest.audio["sha256"]})
    receipt = {"schema_version": 1, "status": "skipped", "evaluated_at": NOW.isoformat(),
               "reason": "insufficient_new_information", "source_health": {"source": "ok:0"},
               "minimum_source_health": 0.6, "last_episode_id": manifest.episode_id}
    save(RUN_PATH, receipt)
    return manifest, receipt


def test_fresh_skip_binds_old_feed_to_exact_confirmed_candidate(monkeypatch, tmp_path):
    manifest, _ = confirmed_skip(monkeypatch, tmp_path)
    assert skip_candidate(now=NOW).to_dict() == manifest.to_dict()


def test_diagnostic_candidate_rows_do_not_turn_a_healthy_skip_into_an_outage(monkeypatch, tmp_path):
    manifest, receipt = confirmed_skip(monkeypatch, tmp_path)
    receipt["source_health"].update({
        "research:arxiv": "ok:0",
        **{f"research:arxiv:paper-{index}": "not_fetched:candidate_limit" for index in range(10)},
    })
    save(RUN_PATH, receipt)
    assert skip_candidate(now=NOW).episode_id == manifest.episode_id


@pytest.mark.parametrize("change", [
    {"status": "failed"}, {"evaluated_at": (NOW - timedelta(hours=26)).isoformat()},
    {"evaluated_at": (NOW + timedelta(hours=1)).isoformat()}, {"source_health": {"source": "error:timeout"}},
    {"last_episode_id": "unexpected"}, {"reason": "quota_exhausted"},
])
def test_skip_receipt_cannot_hide_failure_or_wrong_delivery(monkeypatch, tmp_path, change):
    _, receipt = confirmed_skip(monkeypatch, tmp_path)
    save(RUN_PATH, {**receipt, **change})
    with pytest.raises(PublicationError, match="run receipt"):
        skip_candidate(now=NOW)


def test_missing_skip_receipt_does_not_bypass_normal_feed_freshness(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert skip_candidate(now=NOW) is None


def test_pending_candidate_cannot_be_hidden_by_previous_skip(monkeypatch, tmp_path):
    manifest, _ = confirmed_skip(monkeypatch, tmp_path)
    pending = manifest.to_dict()
    pending.update(episode_id="daily-pending", status="candidate")
    save("data/episodes/daily-pending.json", pending)
    with pytest.raises(PublicationError, match="pending publication"):
        skip_candidate(now=NOW)
