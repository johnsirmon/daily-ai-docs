"""Network-free request, recency, long-form, and mixed-feed contracts."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from unittest.mock import Mock

import pytest

from pipeline import daily
from pipeline.adhoc import authorize, prepare, write_brief
from pipeline.audio import AudioValidationError, analyze_audio, narration_duration_bounds
from pipeline.audio_quality import repetition_findings, validate_quality_report
from pipeline.disclosure import AI_NARRATION_DISCLOSURE
from pipeline.podcast_request import PodcastRequest, record_status, request_from_issue, save_request
from pipeline.rank import score_event, select_editorial_events, select_events
from pipeline.schema import EpisodeManifest, SchemaError, SourceEvent, source_display_label
from tests.test_reviewed_audio import corrected_draft, draft, TIMESTAMP, CLAIM


def request(**changes):
    return PodcastRequest(
        **{"topic": "Agent evaluation", "audience": "Developers", "cutoff": TIMESTAMP,
           "actor": "maintainer", **changes},
    ).validate()


def long_draft(*, ready=False, **changes):
    item = draft()
    req = request(**changes)
    item["schema_version"] = 4
    item["episode_id"] = req.episode_id
    item["narration"] = CLAIM
    item["generation"].update(
        edition="adhoc", provider=req.provider, request=req.to_dict(), request_sha256=req.revision,
        quality={}, voice={},
    )
    item["generation"]["transcript"]["sha256"] = hashlib.sha256(CLAIM.encode()).hexdigest()
    item["audio"]["url"] = (
        f"https://github.com/johnsirmon/daily-ai-docs/releases/download/{req.episode_id}/daily-ai-brief.mp3"
    )
    if ready:
        item["status"] = "ready"
        item["audio"].update(
            size_bytes=12000, duration_secs=1200, sha256="a" * 64,
            codec="mp3", sample_rate=44100, channels=2,
        )
        item["generation"]["quality"] = {
            "method": "ffmpeg_loudnorm_two_pass", "ffmpeg": "ffmpeg test",
            "integrated_lufs": -16, "true_peak_dbtp": -1.1, "audio_sha256": "a" * 64,
        }
    return item


EVERGREEN_CLAIM = "Repository instructions customize agent behavior."
EVERGREEN_CONTENT = EVERGREEN_CLAIM + "\nCopilot agents can use repository instructions in a repository.\n"


def evergreen_event(**changes):
    values = {
        "event_id": "docs:copilot-customization",
        "source_type": "evergreen_documentation",
        "title": "Customize Copilot agents",
        "url": "https://docs.github.com/en/copilot/customizing-copilot",
        "product": "GitHub Copilot",
        "topic": "Coding agents",
        "published_at": "",
        "fetched_at": TIMESTAMP,
        "evidence": EVERGREEN_CLAIM,
        "authority": "primary",
        "metadata": {"evergreen_snapshot": {
            "captured_at": "2026-09-17T18:00:00Z",
            "content_sha256": hashlib.sha256(EVERGREEN_CONTENT.encode("utf-8")).hexdigest(),
            "content": EVERGREEN_CONTENT,
            "reviewer": "assistant",
            "reviewed_at": "2026-09-17T19:00:00Z",
            "review_note": (
                "The official documentation provides no original publication date; the original publication date "
                "is unavailable in the page or its public metadata."
            ),
        }},
    }
    values.update(changes)
    return values


def long_draft_with_evergreen(*, ready=False):
    data = long_draft(ready=ready)
    event = evergreen_event()
    data["source_events"].append(event)
    data["stories"][0]["event_ids"].append(event["event_id"])
    data["stories"][0]["source_urls"].append(event["url"])
    data["narration"] += " " + EVERGREEN_CLAIM
    data["generation"]["transcript"]["sha256"] = hashlib.sha256(data["narration"].encode()).hexdigest()
    data["generation"]["review"]["claims"].append({
        "text": EVERGREEN_CLAIM, "event_id": event["event_id"], "quote": EVERGREEN_CLAIM,
    })
    return data


def replace_evergreen_url(data, url):
    event = data["source_events"][1]
    old_url = event["url"]
    event["url"] = url
    data["stories"][0]["source_urls"] = [
        url if value == old_url else value for value in data["stories"][0]["source_urls"]
    ]
    return data


def long_narration(word_count):
    opening = AI_NARRATION_DISCLOSURE + "\n\n" + CLAIM + "\n\n"
    return opening + " ".join(f"w{index}" for index in range(word_count - len(opening.split())))


def prepare_inputs(tmp_path, *, corrected=False):
    req = request(publish_now=True)
    request_path = save_request(req, tmp_path)
    source = tmp_path / "source.wav"
    source.write_bytes(b"reviewed lossless composite" if corrected else b"original")
    data = draft()
    packet = tmp_path / "packet.json"
    packet.write_text(json.dumps({key: data[key] for key in (
        "source_events", "source_health", "stories", "show_notes",
    )}), encoding="utf-8")
    narration = long_narration(8885 if corrected else 5000)
    review_data = {
        "transcript": {"engine": "faster-whisper", "model": "small.en"},
        "review": data["generation"]["review"], "voice": {},
    }
    if corrected:
        review_data["editing"] = corrected_draft()["generation"]["editing"]
        narration = review_data["editing"]["correction_text"] + "\n\n" + narration
    transcript = tmp_path / "transcript.txt"
    transcript.write_text(narration, encoding="utf-8")
    review = tmp_path / "review.json"
    review.write_text(json.dumps(review_data), encoding="utf-8")
    return request_path, packet, transcript, review, source, tmp_path / "prepared"


@pytest.mark.parametrize("days", [0, 366, True, 1.5, "60"])
def test_request_rejects_invalid_window(days):
    with pytest.raises(ValueError, match="lookback"):
        request(lookback_days=days)


def test_request_identity_binds_intent_provider_and_revision(tmp_path):
    original = request()
    assert request(publish_now=True).request_id != original.request_id
    assert request(provider="edge").request_id != original.request_id
    assert request(lookback_days=90).request_id != original.request_id
    path = save_request(original, tmp_path)
    assert save_request(original, tmp_path) == path
    record_status(path.parent, original, "cancelled")
    with pytest.raises(ValueError, match="terminal"):
        record_status(path.parent, original, "ready")


@pytest.mark.parametrize("days", [60, 90])
@pytest.mark.parametrize("offset,accepted", [(0, True), (-0.001, True), (0.001, False)])
def test_exact_recency_boundary(days, offset, accepted):
    req = request(lookback_days=days)
    event = SourceEvent.from_dict(draft()["source_events"][0])
    end = datetime.fromisoformat(TIMESTAMP.replace("Z", "+00:00"))
    event = replace(event, published_at=(end - timedelta(days=days, seconds=offset)).isoformat())
    if accepted:
        req.validate_sources([event])
    else:
        with pytest.raises(ValueError, match="window"):
            req.validate_sources([event])


def test_recency_rejects_future_unknown_and_secondary():
    req = request()
    event = SourceEvent.from_dict(draft()["source_events"][0])
    for stamp in ("", "2030-01-01T00:00:00Z"):
        event = replace(event, published_at=stamp)
        with pytest.raises(ValueError):
            req.validate_sources([event])
    event = replace(event, published_at=TIMESTAMP, authority="secondary")
    with pytest.raises(ValueError):
        req.validate_sources([event])


def test_reviewed_evergreen_documentation_is_ad_hoc_supporting_evidence(tmp_path):
    from pipeline.render import render_manifest_readme

    data = long_draft_with_evergreen()
    manifest = EpisodeManifest.from_dict(data)
    assert manifest.source_events[1].published_at == ""
    assert EpisodeManifest.from_dict(manifest.to_dict()).to_dict() == manifest.to_dict()
    label = "Evergreen documentation; original publication date unavailable; snapshot reviewed 2026-09-17"
    assert label in render_manifest_readme(manifest)

    req = request(provider="edge")
    packet = {key: data[key] for key in ("source_events", "source_health", "stories", "show_notes")}
    brief = write_brief(req, packet, tmp_path)
    assert label in brief.read_text(encoding="utf-8")


@pytest.mark.parametrize("url", [
    "https://arxiv.org/abs/1706.03762",
    "https://www.reddit.com/r/LocalLLaMA/comments/example/community_study/",
    "https://github.blog/changelog/2024-10-29-github-copilot-in-vscode/",
    "https://docs.github.com/en/actions",
    "https://docs.github.com.evil.example/en/copilot/customizing-copilot",
    "https://docs.github.com/en/copilot/../actions",
    "https://docs.github.com/en/copilot/../../articles",
    "https://docs.github.com/en/copilot/%2e%2e/actions",
    "https://docs.github.com/en/copilot/%252e%252e/actions",
    "https://docs.github.com/en/copilot/.%2E/actions",
    "https://docs.github.com/en/copilot/%2f..%2factions",
    "https://docs.github.com/en/copilot/%5c..%5cactions",
    "https://docs.github.com/en/copilot\\..\\actions",
    "https://docs.github.com/en/copilot//actions",
    "https://docs.github.com/en/copilot//",
    "https://docs.github.com/en/copilot/\tactions",
])
def test_non_documentation_urls_cannot_be_relabelled_evergreen_in_manifest(url):
    with pytest.raises(SchemaError, match="approved official documentation path"):
        EpisodeManifest.from_dict(replace_evergreen_url(long_draft_with_evergreen(), url))


@pytest.mark.parametrize("url", [
    "https://docs.github.com/en/copilot",
    "https://docs.github.com/en/copilot/",
    "https://docs.github.com/en/copilot/customizing-copilot",
])
def test_canonical_evergreen_documentation_paths_preserve_source_identity(url):
    manifest = EpisodeManifest.from_dict(replace_evergreen_url(long_draft_with_evergreen(), url))
    assert manifest.source_events[1].url == url
    assert manifest.to_dict()["source_events"][1]["url"] == url


def test_evergreen_path_policy_preserves_normal_fragment_encoding():
    url = "https://docs.github.com/en/copilot/customizing-copilot#customize%20copilot"
    event = SourceEvent.from_dict(evergreen_event(url=url))
    assert event.url == url
    assert event.to_dict()["url"] == url


@pytest.mark.parametrize("url,accepted", [
    ("https://docs.github.com/en/copilot/customizing-copilot", True),
    ("https://docs.github.com/en/copilot/../actions", False),
    ("https://docs.github.com/en/copilot/%2e%2e/actions", False),
    ("https://docs.github.com/en/copilot/%2f..%2factions", False),
    ("https://docs.github.com/en/copilot\\..\\actions", False),
    ("https://arxiv.org/abs/1706.03762", False),
    ("https://www.reddit.com/r/LocalLLaMA/comments/example/community_study/", False),
    ("https://github.blog/changelog/2024-10-29-github-copilot-in-vscode/", False),
])
def test_prepare_enforces_evergreen_documentation_url_policy(url, accepted, tmp_path, monkeypatch):
    data = replace_evergreen_url(long_draft_with_evergreen(), url)
    req = request()
    request_path = save_request(req, tmp_path)
    packet = tmp_path / "packet.json"
    packet.write_text(json.dumps({key: data[key] for key in (
        "source_events", "source_health", "stories", "show_notes",
    )}), encoding="utf-8")
    transcript = tmp_path / "transcript.txt"
    transcript.write_text(data["narration"], encoding="utf-8")
    review = tmp_path / "review.json"
    review.write_text(json.dumps({key: data["generation"][key] for key in (
        "transcript", "review", "voice",
    )}), encoding="utf-8")
    audio = tmp_path / "original.wav"
    audio.write_bytes(b"synthetic reviewed audio")
    importer = Mock(return_value={"episode_id": req.episode_id})
    monkeypatch.setattr("pipeline.reviewed_audio.prepare_reviewed_audio", importer)
    if accepted:
        result = prepare(request_path, packet, transcript, review, audio, tmp_path / "prepared")
        assert result["episode_id"] == req.episode_id
        importer.assert_called_once()
    else:
        with pytest.raises(SchemaError, match="approved official documentation path"):
            prepare(request_path, packet, transcript, review, audio, tmp_path / "prepared")
        importer.assert_not_called()


def test_subscriber_descriptions_label_evergreen_sources_with_and_without_catalog(tmp_path):
    from pipeline.podcast import load_episodes, write_feed
    from pipeline.podcast_metadata import manifest_presentation

    data = long_draft_with_evergreen()
    data["show_notes"] += "\nSources: " + data["source_events"][1]["url"]
    manifest = EpisodeManifest.from_dict(data)
    label = source_display_label(manifest.source_events[1])
    before = manifest.to_dict()
    assert label in manifest_presentation(manifest, metadata_path=None)["description"]
    catalog = tmp_path / "metadata.json"
    catalog.write_text(json.dumps({"schema_version": 1, "episodes": {manifest.episode_id: {
        "title": "Reviewed evergreen presentation",
        "summary": "Reviewed subscriber summary.",
        "evidence_url": "https://github.com/johnsirmon/daily-ai-docs/blob/" + "a" * 40 + "/podcast.xml",
    }}}), encoding="utf-8")
    presentation = manifest_presentation(manifest, metadata_path=catalog)
    assert label in presentation["description"]
    feed = tmp_path / "podcast.xml"
    write_feed([{
        "guid": manifest.episode_id,
        "title": presentation["title"],
        "pub_date": manifest.published_at,
        "mp3_url": manifest.audio["url"],
        "file_size_bytes": 12000,
        "duration_secs": 1200,
        "description": presentation["description"],
    }], str(feed))
    assert label in load_episodes(str(feed))[0]["description"]
    assert manifest.to_dict() == before


def test_evergreen_documentation_does_not_satisfy_dated_primary_minimum():
    event = SourceEvent.from_dict(evergreen_event())
    with pytest.raises(ValueError, match="insufficient dated primary evidence"):
        request().validate_sources([event])


def test_evergreen_documentation_is_excluded_from_daily_selection():
    event = SourceEvent.from_dict(evergreen_event())
    with pytest.raises(ValueError, match="not eligible for daily news scoring"):
        score_event(event)
    selected, notes = select_events([event], minimum_score=0)
    assert selected == [] and "ad-hoc supporting evidence only" in notes[0]
    selected, notes = select_editorial_events(
        [event], now=datetime.fromisoformat(TIMESTAMP.replace("Z", "+00:00")),
    )
    assert selected == [] and "ad-hoc supporting evidence only" in notes[0]


def test_evergreen_documentation_is_rejected_from_daily_manifest():
    data = draft()
    data["source_events"][0] = evergreen_event()
    data["stories"][0]["event_ids"] = [data["source_events"][0]["event_id"]]
    data["stories"][0]["source_urls"] = [data["source_events"][0]["url"]]
    with pytest.raises(SchemaError, match="ad-hoc requests only"):
        EpisodeManifest.from_dict(data)


@pytest.mark.parametrize("field,value,match", [
    ("captured_at", "2026-09-17T18:00:00-04:00", "UTC timestamp"),
    ("reviewed_at", "2026-09-17T17:00:00Z", "cannot predate"),
    ("reviewer", "", "must not be empty"),
    ("content_sha256", "A" * 64, "lowercase SHA-256"),
    ("review_note", "Reviewed official docs.", "original publication date"),
])
def test_evergreen_snapshot_rejects_malformed_review_provenance(field, value, match):
    event = evergreen_event()
    event["metadata"]["evergreen_snapshot"][field] = value
    with pytest.raises(SchemaError, match=match):
        SourceEvent.from_dict(event)


def test_evergreen_snapshot_rejects_missing_and_tampered_content():
    missing = evergreen_event()
    missing["metadata"] = {}
    with pytest.raises(SchemaError, match="evergreen_snapshot"):
        SourceEvent.from_dict(missing)
    tampered = evergreen_event()
    tampered["metadata"]["evergreen_snapshot"]["content"] += "Tampered"
    with pytest.raises(SchemaError, match="exact UTF-8 content"):
        SourceEvent.from_dict(tampered)
    unbound = evergreen_event(evidence="A claim absent from the captured document.")
    with pytest.raises(SchemaError, match="exact excerpt"):
        SourceEvent.from_dict(unbound)
    dishonest = evergreen_event(published_at=TIMESTAMP)
    with pytest.raises(SchemaError, match="must be empty"):
        SourceEvent.from_dict(dishonest)

    missing_review = evergreen_event()
    del missing_review["metadata"]["evergreen_snapshot"]["reviewed_at"]
    with pytest.raises(SchemaError, match="evergreen_snapshot"):
        SourceEvent.from_dict(missing_review)

    oversized = evergreen_event()
    oversized_content = "x" * 80001
    oversized["metadata"]["evergreen_snapshot"]["content"] = oversized_content
    oversized["metadata"]["evergreen_snapshot"]["content_sha256"] = hashlib.sha256(
        oversized_content.encode("utf-8"),
    ).hexdigest()
    with pytest.raises(SchemaError, match="80000 UTF-8 bytes"):
        SourceEvent.from_dict(oversized)


def test_evergreen_snapshot_is_bound_to_manifest_bytes_and_replay_validation():
    original = EpisodeManifest.from_dict(long_draft_with_evergreen()).to_dict()
    original_bytes = json.dumps(original, sort_keys=True, separators=(",", ":")).encode("utf-8")
    changed = deepcopy(original)
    snapshot = changed["source_events"][1]["metadata"]["evergreen_snapshot"]
    snapshot["content"] += "Reviewed addition."
    snapshot["content_sha256"] = hashlib.sha256(snapshot["content"].encode("utf-8")).hexdigest()
    replay = EpisodeManifest.from_dict(changed).to_dict()
    replay_bytes = json.dumps(replay, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert hashlib.sha256(original_bytes).hexdigest() != hashlib.sha256(replay_bytes).hexdigest()

    tampered = deepcopy(original)
    tampered["source_events"][1]["metadata"]["evergreen_snapshot"]["content"] += "tamper"
    with pytest.raises(SchemaError, match="exact UTF-8 content"):
        EpisodeManifest.from_dict(tampered)


def test_long_form_does_not_change_old_serialization():
    for data in (draft(), long_draft()):
        manifest = EpisodeManifest.from_dict(data)
        serialized = manifest.to_dict()
        assert serialized["generation"] == data["generation"]
        assert EpisodeManifest.from_dict(serialized).to_dict() == serialized
        assert "editing" not in manifest.generation


@pytest.mark.parametrize("words", [10000, 10001])
def test_long_form_narration_word_boundary(words):
    data = long_draft()
    data["narration"] = long_narration(words)
    assert len(data["narration"].split()) == words
    assert len(data["narration"]) < 60000
    data["generation"]["transcript"]["sha256"] = hashlib.sha256(data["narration"].encode()).hexdigest()
    if words == 10001:
        with pytest.raises(SchemaError, match="10000-word long-form budget"):
            EpisodeManifest.from_dict(data)
    else:
        assert EpisodeManifest.from_dict(data).narration == data["narration"]


@pytest.mark.parametrize("characters", [60000, 60001])
@pytest.mark.parametrize("padding", ["x", " "])
def test_long_form_narration_character_boundary(characters, padding):
    data = long_draft()
    data["narration"] += padding * (characters - len(data["narration"]))
    data["generation"]["transcript"]["sha256"] = hashlib.sha256(data["narration"].encode()).hexdigest()
    if characters == 60001:
        with pytest.raises(SchemaError, match="narration exceeds 60000 characters"):
            EpisodeManifest.from_dict(data)
    else:
        assert EpisodeManifest.from_dict(data).narration == data["narration"]


@pytest.mark.parametrize("schema", [1, 2, 3])
@pytest.mark.parametrize("narration,error", [
    (long_narration(1501), "ten-minute word budget"),
    ("x" * 16001, "narration exceeds 16000 characters"),
], ids=["1501-words", "16001-characters"])
def test_daily_narration_budgets_are_not_widened(schema, narration, error):
    data = draft()
    data.update(schema_version=schema, narration=narration)
    with pytest.raises(SchemaError, match=error):
        EpisodeManifest.from_dict(data)


@pytest.mark.parametrize("schema", [1, 3])
@pytest.mark.parametrize("narration", [
    long_narration(1500), CLAIM + "x" * (16000 - len(CLAIM)),
], ids=["1500-words", "16000-characters"])
def test_daily_narration_boundaries_remain_accepted(schema, narration):
    data = draft()
    data.update(schema_version=schema, narration=narration)
    data["generation"]["transcript"]["sha256"] = hashlib.sha256(narration.encode()).hexdigest()
    assert EpisodeManifest.from_dict(data).narration == narration


@pytest.mark.parametrize("output_exists", [False, True])
@pytest.mark.parametrize("field,value", [
    ("method", "trimmed_conversation"), ("correction_provider", "gemini"),
    ("original_audio_sha256", "invalid"), ("original_audio_sha256", "A" * 64),
    ("correction_audio_sha256", None), ("correction_audio_sha256", "f" * 63),
    ("correction_text", ""), ("correction_text", "not the actual prefix"),
    ("correction_text", "x" * 1601), ("verified", True),
])
def test_prepare_rejects_invalid_editing_before_import_or_resume(
        monkeypatch, tmp_path, output_exists, field, value):
    from pipeline.adhoc import prepare
    inputs = prepare_inputs(tmp_path, corrected=True)
    review = json.loads(inputs[3].read_text())
    review["editing"][field] = value
    inputs[3].write_text(json.dumps(review), encoding="utf-8")
    if output_exists:
        inputs[-1].mkdir()
    importer, resume = Mock(), Mock()
    monkeypatch.setattr("pipeline.reviewed_audio.prepare_reviewed_audio", importer)
    monkeypatch.setattr("pipeline.daily.resume_reviewed_release", resume)
    with pytest.raises(SchemaError):
        prepare(*inputs)
    importer.assert_not_called()
    resume.assert_not_called()
    assert not list(inputs[0].parent.glob("draft-*.json"))


@pytest.mark.parametrize("editing", [None, [], {}, {"method": "prefixed_editorial_correction"}])
def test_prepare_rejects_incomplete_editing(monkeypatch, tmp_path, editing):
    from pipeline.adhoc import prepare
    inputs = prepare_inputs(tmp_path, corrected=True)
    review = json.loads(inputs[3].read_text())
    review["editing"] = editing
    inputs[3].write_text(json.dumps(review), encoding="utf-8")
    importer = Mock()
    monkeypatch.setattr("pipeline.reviewed_audio.prepare_reviewed_audio", importer)
    with pytest.raises(SchemaError, match="generation.editing"):
        prepare(*inputs)
    importer.assert_not_called()
    assert not inputs[-1].exists()


@pytest.mark.parametrize("field", ["transcript", "review", "voice", "unsupported"])
def test_prepare_keeps_review_fields_exact(monkeypatch, tmp_path, field):
    from pipeline.adhoc import prepare
    inputs = prepare_inputs(tmp_path)
    review = json.loads(inputs[3].read_text())
    if field == "unsupported":
        review[field] = {}
    else:
        review.pop(field)
    inputs[3].write_text(json.dumps(review), encoding="utf-8")
    importer = Mock()
    monkeypatch.setattr("pipeline.reviewed_audio.prepare_reviewed_audio", importer)
    with pytest.raises(ValueError, match="review requires"):
        prepare(*inputs)
    importer.assert_not_called()
    assert not inputs[-1].exists()


@pytest.mark.parametrize("seconds", [1, 1150.897, 1199.999, 1200, 1800, 1800.001, 1912.442, 2996])
def test_long_form_measured_duration_contract(seconds):
    data = long_draft(ready=True)
    data["audio"]["duration_secs"] = seconds
    manifest = EpisodeManifest.from_dict(data)
    assert manifest.audio == data["audio"]
    assert manifest.to_dict() == EpisodeManifest.from_dict(manifest.to_dict()).to_dict()


@pytest.mark.parametrize("seconds", [0, -1, True, "1912.442", None, float("nan"), float("inf"), -float("inf")])
def test_long_form_rejects_invalid_duration(seconds):
    data = long_draft(ready=True)
    data["audio"]["duration_secs"] = seconds
    with pytest.raises(SchemaError, match="finite positive"):
        EpisodeManifest.from_dict(data)


def test_long_form_request_and_provider_cannot_be_tampered():
    for key, value in (("request_sha256", "b" * 64), ("provider", "edge"), ("edition", "notebook")):
        data = long_draft()
        data["generation"][key] = value
        with pytest.raises(SchemaError):
            EpisodeManifest.from_dict(data)


def test_preview_cannot_finalize_before_any_feed_write(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(long_draft(ready=True)))
    with pytest.raises(RuntimeError, match="preview"):
        daily.finalize(path, verify_remote=False, publication_path=tmp_path / "unused.json")
    assert not Path("podcast.xml").exists()


def test_issue_parsing_does_not_execute_text(monkeypatch):
    body = """### Topic
$(touch injected); evaluation
### Audience
Developers
### Evidence window (days)
90
### Audio provider
gemini-notebook-web
### Publication
Publish when all gates pass
"""
    issue = {"number": 10, "body": body, "created_at": TIMESTAMP, "user": {"login": "maintainer"}}
    req = request_from_issue(issue)
    assert req.topic.startswith("$(touch")
    assert req.lookback_days == 90 and req.publish_now
    monkeypatch.setattr("pipeline.adhoc.github", lambda *args: '{"permission":"read"}')
    with pytest.raises(PermissionError):
        authorize(req, publishing=True)


def test_issue_edit_invalidates_authorization(monkeypatch):
    req = request(issue=5, publish_now=True)
    monkeypatch.setattr("pipeline.adhoc.github", lambda *args: (
        '{"permission":"write"}' if args[1].endswith("/permission") else '{"state":"closed"}'
    ))
    with pytest.raises(PermissionError, match="closed"):
        authorize(req, publishing=True)


def test_brief_is_source_bounded_and_request_local(tmp_path):
    req = request()
    path = save_request(req, tmp_path)
    brief = write_brief(req, draft(), path.parent)
    assert "20-30 minutes as an editorial target, not a publication limit" in brief.read_text()
    assert "A shorter or longer recording is acceptable" in brief.read_text()
    assert "2026-07-19" in brief.read_text()
    assert not (tmp_path / "episode-manifest.json").exists()


def test_adjacent_repeat_detection_and_natural_reuse():
    passage = "one two three four five six seven eight nine ten eleven twelve"
    assert repetition_findings(passage + " " + passage)
    assert not repetition_findings("The tool changed. Another tool changed in a different way.")


@pytest.mark.parametrize("field,value", [
    ("integrated_lufs", -17.01), ("integrated_lufs", -14.99),
    ("true_peak_dbtp", -0.99), ("integrated_lufs", float("nan")),
    ("audio_sha256", "b" * 64),
])
def test_quality_report_fails_closed(field, value):
    report = long_draft(ready=True)["generation"]["quality"]
    report[field] = value
    with pytest.raises(ValueError):
        validate_quality_report(report, final=True, audio_sha256="a" * 64)


@pytest.mark.parametrize("seconds", [1150.897, 1200, 1912.442, 2996])
def test_adhoc_confirmation_preserves_daily_cadence_and_run(monkeypatch, tmp_path, seconds):
    monkeypatch.chdir(tmp_path)
    state = {
        "schema_version": 1, "seen_event_ids": [], "last_episode_id": "daily-previous",
        "last_publication": "2026-09-16T00:00:00Z", "repo_snapshots": {},
    }
    daily._save_json(Path("data/state.json"), state)
    daily._save_json(Path("data/runs/latest.json"), {"unchanged": True})
    data = long_draft(ready=True, publish_now=True)
    data["audio"]["duration_secs"] = seconds
    manifest = EpisodeManifest.from_dict(data)
    manifest.status = "candidate"
    daily._save_json(Path("data/episodes") / f"{manifest.episode_id}.json", manifest.to_dict())
    daily.confirm(manifest.episode_id, verify_remote=False)
    after = daily.load_state()
    assert after["schema_version"] == 2
    assert after["last_daily_publication"] == state["last_publication"]
    assert after["last_daily_episode_id"] == state["last_episode_id"]
    assert after["last_episode_id"] == manifest.episode_id
    assert json.loads(Path("data/runs/latest.json").read_text()) == {"unchanged": True}
    req = request(publish_now=True)
    receipt = Path("data/requests") / f"{req.request_id}.json"
    assert json.loads(receipt.read_text())["status"] == "published"
    daily.confirm(manifest.episode_id, verify_remote=False)
    assert len(list(Path("data/receipts").glob("*.json"))) == 1


def test_unsupported_voice_provider_is_rejected():
    with pytest.raises(ValueError, match="unsupported requested audio provider"):
        request(provider="local")


def mixed_history(tmp_path, *, status="skipped"):
    previous = draft()
    previous["status"] = "published"
    previous["audio"].update(
        size_bytes=12000, duration_secs=400, sha256="b" * 64,
        codec="mp3", sample_rate=44100, channels=2,
    )
    old = EpisodeManifest.from_dict(previous)
    special = EpisodeManifest.from_dict(long_draft(ready=True, publish_now=True))
    special.status = "published"
    for manifest in (old, special):
        daily._save_json(Path("data/episodes") / f"{manifest.episode_id}.json", manifest.to_dict())
        daily._save_json(Path("data/receipts") / f"{manifest.episode_id}.json", {
            "episode_id": manifest.episode_id, "audio_sha256": manifest.audio["sha256"],
        })
    daily._save_json(Path("data/state.json"), {
        "schema_version": 2, "seen_event_ids": ["e1"],
        "last_episode_id": special.episode_id, "last_publication": special.published_at,
        "last_daily_episode_id": old.episode_id, "last_daily_publication": old.published_at,
    })
    daily._save_json(Path("data/runs/latest.json"), {
        "schema_version": 1, "status": status, "evaluated_at": TIMESTAMP,
        "reason": "insufficient_new_information", "source_health": {"manual:source": "ok:1"},
        "minimum_source_health": 0.6, "last_episode_id": old.episode_id,
    })
    return old, special


@pytest.mark.parametrize("status", ["skipped", "published"])
def test_mixed_feed_monitors_latest_special_and_daily_evaluation(monkeypatch, tmp_path, status):
    from pipeline.run_health import skip_candidate
    monkeypatch.chdir(tmp_path)
    _, special = mixed_history(tmp_path, status=status)
    result = skip_candidate(now=datetime.fromisoformat(TIMESTAMP.replace("Z", "+00:00")))
    assert result.episode_id == special.episode_id


def test_fresh_special_cannot_hide_failed_daily(monkeypatch, tmp_path):
    from pipeline.run_health import skip_candidate
    monkeypatch.chdir(tmp_path)
    mixed_history(tmp_path, status="failed")
    with pytest.raises(RuntimeError, match="failed"):
        skip_candidate(now=datetime.fromisoformat(TIMESTAMP.replace("Z", "+00:00")))


def test_paper_daily_policy_is_not_widened():
    from pipeline.sources.papers import collect_research_papers
    events, health = collect_research_papers({"enabled": True, "lookback_days": 60})
    assert not events and health["research:arxiv"].startswith("error:")


def test_special_display_copy_does_not_change_reviewed_contract():
    from pipeline.podcast_metadata import manifest_presentation
    manifest = EpisodeManifest.from_dict(long_draft(ready=True, publish_now=True))
    before = manifest.to_dict()
    presentation = manifest_presentation(manifest)
    assert presentation["title"] == manifest.generation["request"]["topic"]
    assert "Special episode" in presentation["description"]
    assert presentation["description"].endswith(manifest.show_notes)
    assert manifest.to_dict() == before


def test_special_reserved_art_is_display_only(tmp_path):
    from pipeline.podcast_metadata import manifest_presentation
    manifest = EpisodeManifest.from_dict(long_draft(ready=True, publish_now=True))
    before = manifest.to_dict()
    image_url = "https://johnsirmon.github.io/daily-ai-docs/assets/episodes/special-v1.jpg"
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({
        "schema_version": 1, "episodes": {manifest.episode_id: {"image_url": image_url}},
    }))
    presentation = manifest_presentation(manifest, metadata_path=catalog)
    assert presentation["image_url"] == image_url
    assert "Special episode" in presentation["description"]
    assert manifest.to_dict() == before


def test_duplicate_issue_form_fields_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        request_from_issue({"body": "### Topic\nA\n### Topic\nB"})


def test_daily_cadence_uses_daily_timestamp_not_special(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    mixed_history(tmp_path)
    state = daily.load_state()
    state["last_daily_publication"] = "2026-09-16T00:00:00Z"
    daily._save_json(Path("data/state.json"), state)
    config = Path("topics.yaml")
    config.write_text("daily: {}\n", encoding="utf-8")
    def collected(*args, **kwargs):
        raise RuntimeError("collector reached")
    monkeypatch.setattr(daily, "collect_events", collected)
    monkeypatch.setenv("AI_EDITORIAL", "off")
    with pytest.raises(RuntimeError, match="collector reached"):
        daily.prepare(config, now=datetime.fromisoformat(TIMESTAMP.replace("Z", "+00:00")))


def test_request_receipt_recovers_after_confirmation_interruption(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    manifest = EpisodeManifest.from_dict(long_draft(ready=True, publish_now=True))
    manifest.status = "candidate"
    daily._save_json(Path("data/episodes") / f"{manifest.episode_id}.json", manifest.to_dict())
    daily.confirm(manifest.episode_id, verify_remote=False)
    receipt = Path("data/requests") / f"{request(publish_now=True).request_id}.json"
    receipt.unlink()
    daily.confirm(manifest.episode_id, verify_remote=False)
    assert json.loads(receipt.read_text())["status"] == "published"


@pytest.mark.parametrize("seconds,accepted,corrected", [
    (1150.897, True, False), (1200, True, False), (1800, True, False),
    (1912.442, True, False), (2996, True, False), (2996, True, True),
    (1, False, False), (10000, False, False),
])
def test_prepare_import_and_exact_bundle_resume(monkeypatch, tmp_path, seconds, accepted, corrected):
    from pipeline.adhoc import prepare
    monkeypatch.chdir(tmp_path)
    req = request(publish_now=True)
    request_path, packet, transcript, review, source, target = prepare_inputs(tmp_path, corrected=corrected)
    narration = transcript.read_text(encoding="utf-8")
    original_audio = source.read_bytes()
    original_review = json.loads(review.read_text())
    content = b"x" * 12000
    digest = hashlib.sha256(content).hexdigest()
    report = {**long_draft(ready=True)["generation"]["quality"], "audio_sha256": digest}
    def master(source, target):
        assert source.read_bytes() == original_audio
        target.write_bytes(content)
        return report
    commands = []
    def media_run(command, **kwargs):
        commands.append(command)
        payload = {"format": {"duration": str(seconds)}, "streams": [
            {"codec_name": "mp3", "sample_rate": 44100, "channels": 2},
        ]}
        return subprocess.CompletedProcess(
            command, 0, stdout=json.dumps(payload) if command[0] == "ffprobe" else "", stderr="",
        )
    def measured(path, **kwargs):
        assert (kwargs["min_duration_secs"], kwargs["max_duration_secs"]) == narration_duration_bounds(
            len(narration.split()),
        )
        assert kwargs["expected_word_count"] == len(narration.split())
        assert kwargs.get("full_decode", True)
        return analyze_audio(path, **kwargs)
    monkeypatch.setattr("pipeline.audio_quality.master_audio", master)
    monkeypatch.setattr("pipeline.reviewed_audio.shutil.which", lambda name: name)
    monkeypatch.setattr("pipeline.audio.subprocess.run", media_run)
    monkeypatch.setattr("pipeline.reviewed_audio.analyze_audio", measured)
    monkeypatch.setattr("pipeline.daily.analyze_audio", measured)
    monkeypatch.setattr("pipeline.audio_quality.loudness", lambda *args: {"input_i": -16, "input_tp": -1.1})
    if not accepted:
        with pytest.raises(AudioValidationError, match="outside"):
            prepare(request_path, packet, transcript, review, source, target)
        assert not (target / "episode-manifest.json").exists()
        assert not (target / "publication.json").exists()
        assert not Path("podcast.xml").exists()
        assert not Path("data/state.json").exists()
        return
    first = prepare(request_path, packet, transcript, review, source, target)
    manifest_bytes = (target / "episode-manifest.json").read_bytes()
    second = prepare(request_path, packet, transcript, review, source, target)
    assert first["episode_id"] == second["episode_id"] == req.episode_id
    assert second["resumed"]
    assert source.read_bytes() == original_audio
    assert (target / "episode-manifest.json").read_bytes() == manifest_bytes
    assert (target / "daily-ai-brief.mp3").read_bytes() == content
    prepared = EpisodeManifest.from_dict(json.loads(manifest_bytes))
    assert prepared.narration == narration
    assert prepared.generation["source_audio_sha256"] == hashlib.sha256(original_audio).hexdigest()
    assert prepared.generation["transcript"]["sha256"] == hashlib.sha256(narration.encode()).hexdigest()
    assert EpisodeManifest.from_dict(prepared.to_dict()).to_dict() == prepared.to_dict()
    from pipeline.narrate import manifest_to_narration
    from pipeline.render import render_manifest_readme
    assert manifest_to_narration(prepared) == narration
    if corrected:
        assert prepared.generation["editing"] == original_review["editing"]
        assert narration.endswith(long_narration(8885))
        assert "### Editorial correction" in render_manifest_readme(prepared)
        assert original_review["editing"]["correction_text"] in render_manifest_readme(prepared)
    else:
        assert "editing" not in prepared.generation
        assert "### Editorial correction" not in render_manifest_readme(prepared)
    assert not Path("podcast.xml").exists()
    candidate = daily.finalize(
        target / "episode-manifest.json", verify_remote=False,
        publication_path=target / "publication.json",
    )
    assert candidate.audio["duration_secs"] == seconds
    assert candidate.audio["sha256"] == digest
    from pipeline.podcast import load_episodes
    assert load_episodes()[0]["duration_secs"] == round(seconds)
    assert sum("-xerror" in command for command in commands) == 3
    assert sum("-af" in command for command in commands) == 3
    assert not Path("data/state.json").exists()
    changed_reviews = []
    if corrected:
        removed = {key: value for key, value in original_review.items() if key != "editing"}
        changed_reviews.append(removed)
        for field in ("original_audio_sha256", "correction_audio_sha256", "correction_text"):
            changed = json.loads(json.dumps(original_review))
            changed["editing"][field] = (
                "Editorial correction:" if field == "correction_text" else "0" * 64
            )
            changed_reviews.append(changed)
    else:
        added = {**original_review, "editing": {
            **corrected_draft()["generation"]["editing"], "correction_text": AI_NARRATION_DISCLOSURE,
        }}
        changed_reviews.append(added)
    resume, importer = Mock(), Mock()
    monkeypatch.setattr("pipeline.daily.resume_reviewed_release", resume)
    monkeypatch.setattr("pipeline.reviewed_audio.prepare_reviewed_audio", importer)
    for changed in changed_reviews:
        review.write_text(json.dumps(changed), encoding="utf-8")
        with pytest.raises(ValueError, match="editing provenance changed"):
            prepare(request_path, packet, transcript, review, source, target)
        assert (target / "episode-manifest.json").read_bytes() == manifest_bytes
        assert (target / "daily-ai-brief.mp3").read_bytes() == content
    resume.assert_not_called()
    importer.assert_not_called()


def test_explicit_voice_synthesis_preserves_provider_and_cannot_publish(monkeypatch, tmp_path):
    from pipeline.adhoc import synthesize
    req = request(provider="edge")
    script = tmp_path / "script.txt"
    script.write_text(CLAIM, encoding="utf-8")
    output = tmp_path / "source.mp3"
    monkeypatch.setenv("TTS_PROVIDER", "openai")
    monkeypatch.setattr("pipeline.tts.generate_audio", lambda text: b"x" * 12000)
    synthesize(req, script, output)
    import os
    assert os.environ["TTS_PROVIDER"] == "openai"
    assert output.with_suffix(".voice.json").exists()
    assert not (tmp_path / "podcast.xml").exists()
    with pytest.raises(FileExistsError):
        synthesize(req, script, output)
    with pytest.raises(ValueError, match="browser"):
        synthesize(request(), script, tmp_path / "other.mp3")


@pytest.mark.parametrize("text,accepted", [
    (long_narration(10000), True), (long_narration(10001), False),
    (CLAIM + "x" * (60000 - len(CLAIM)), True),
    (CLAIM + "x" * (60001 - len(CLAIM)), False),
], ids=["10000-words", "10001-words", "60000-characters", "60001-characters"])
def test_explicit_voice_uses_same_long_form_budget(monkeypatch, tmp_path, text, accepted):
    from pipeline.adhoc import synthesize
    script = tmp_path / "script.txt"
    script.write_text(text, encoding="utf-8")
    output = tmp_path / "source.mp3"
    generate = Mock(return_value=b"offline sample")
    monkeypatch.setattr("pipeline.tts.generate_audio", generate)
    if accepted:
        synthesize(request(provider="edge"), script, output)
        generate.assert_called_once_with(text)
        assert output.read_bytes() == b"offline sample"
    else:
        with pytest.raises(ValueError, match="long-form budget"):
            synthesize(request(provider="edge"), script, output)
        generate.assert_not_called()
        assert not output.exists()
        assert not output.with_suffix(".voice.json").exists()
