from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from pipeline import studio
from pipeline.schema import EpisodeManifest, SchemaError
from pipeline.usefulness import spoken_quality_findings, publication_usefulness_findings
from pipeline.rank import select_editorial_events
from pipeline.sources.github import collect_github_releases
from tests.test_reviewed_audio import draft
from tests.test_sources import Response


def edge_draft():
    data = draft()
    data["generation"].update(edition="reviewed-edge", provider="edge", quality={},
                              voice={"name": "en-US-AndrewMultilingualNeural", "rate": "-5%", "pitch": "+0Hz"})
    return data


def test_reviewed_edge_is_explicit_and_does_not_weaken_api_gate():
    item = EpisodeManifest.from_dict(edge_draft())
    assert "fresh briefing is not grounded independently verified editorial" in publication_usefulness_findings(item)
    from pipeline.render import render_manifest_readme
    text = render_manifest_readme(item)
    assert "reviewed Edge narration" in text
    assert "uses user-authorized Gemini Notebook" not in text


@pytest.mark.parametrize("change", [
    lambda d: d["generation"].update(provider="gemini-notebook-web"),
    lambda d: d["generation"].pop("voice"),
    lambda d: d["generation"].pop("quality"),
    lambda d: d["generation"]["voice"].update(secret="private"),
    lambda d: d["generation"]["transcript"].update(sha256="0" * 64),
])
def test_edge_review_provenance_cannot_be_mislabeled_or_incomplete(change):
    data = edge_draft()
    change(data)
    with pytest.raises((SchemaError, ValueError)):
        EpisodeManifest.from_dict(data)


@pytest.mark.parametrize("text", [
    "Update version 1.2.3 then version 1.2.4 then version 1.2.5.",
    "No additional workflow change is supported beyond the cited evidence.",
    "Supplementary learning coverage was unavailable.",
    "Fixes approved in PR #12345.",
])
def test_release_recitation_and_internal_diagnostics_are_not_speech(text):
    assert spoken_quality_findings(text)


def test_a_necessary_version_is_not_a_ban_on_numbers():
    assert spoken_quality_findings("Check whether version 1.2.3 is installed before testing this fix.") == []


def test_synthesis_requires_network_confirmation_before_io(tmp_path):
    with pytest.raises(ValueError, match="confirmed"):
        studio.synthesize(tmp_path / "missing", tmp_path / "output")


def test_synthesis_retries_free_provider_then_reuses_exact_bytes(monkeypatch, tmp_path):
    script = tmp_path / "script.txt"
    script.write_text("A practical agent integration check. " * 30)
    output = tmp_path / "recording"
    calls = []
    def render(text, path):
        import os
        assert os.environ["TTS_PROVIDER"] == "edge"
        calls.append(path)
        if len(calls) == 1:
            return None
        Path(path).write_bytes(b"recording")
        return Path(path)
    monkeypatch.setenv("TTS_PROVIDER", "openai")
    monkeypatch.setattr(studio, "write_audio", render)
    monkeypatch.setattr(studio, "analyze_audio", lambda *a, **k: {})
    monkeypatch.setattr(studio.time, "sleep", lambda delay: None)
    first = studio.synthesize(script, output, confirmed=True)
    assert first["attempts"] == 2
    assert studio.synthesize(script, output, confirmed=True) == first
    assert len(calls) == 2
    assert __import__("os").environ["TTS_PROVIDER"] == "openai"
    script.write_text(script.read_text() + "Changed.")
    with pytest.raises(ValueError, match="changed script"):
        studio.synthesize(script, output, confirmed=True)


def test_failed_synthesis_budget_survives_resume(monkeypatch, tmp_path):
    script = tmp_path / "script.txt"
    script.write_text("A practical agent integration check. " * 30)
    calls = []
    monkeypatch.setattr(studio, "write_audio", lambda *a: calls.append(a))
    monkeypatch.setattr(studio.time, "sleep", lambda delay: None)
    for _ in range(2):
        with pytest.raises(RuntimeError, match="three attempts"):
            studio.synthesize(script, tmp_path / "output", confirmed=True)
    assert len(calls) == 3
    assert json.loads((tmp_path / "output/synthesis.json").read_text())["status"] == "provider_unavailable"


def test_unrelated_output_and_concurrent_owner_are_preserved(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    marker = output / "existing.txt"
    marker.write_text("keep")
    with pytest.raises(ValueError, match="unrelated"):
        with studio._owner(output):
            pass
    assert marker.read_text() == "keep"
    (output / "synthesis.json").write_text("{}")
    with studio._owner(output):
        with pytest.raises(FileExistsError):
            with studio._owner(output):
                pass


def test_official_copilot_source_admits_supported_change_but_not_tag_churn():
    from datetime import datetime, timezone
    root = Path(__file__).resolve().parents[1]
    sources = yaml.safe_load((root / "topics/topics.yaml").read_text())["daily"]["sources"]["github_releases"]
    source = next(row for row in sources if row["repo"] == "github/copilot-cli")
    class Session:
        def get(self, url, **kwargs):
            if url.endswith("repos/github/copilot-cli"):
                return Response({"private": False, "visibility": "public"})
            return Response([{
                "draft": False, "prerelease": prerelease, "published_at": "2026-09-30T21:38:30Z",
                "html_url": "https://github.com/github/copilot-cli/releases/tag/" + tag,
                "tag_name": tag, "body": body,
            } for tag, body, prerelease in [
                ("v1.0.90", "MCP tools recover after transient discovery failures without restarting the session; unchanged catalogs remain available during recovery.", False),
                ("v1.0.91-0", "Release 1.0.91-0", True),
            ]])
    now = datetime(2026,10,1,12,tzinfo=timezone.utc)
    events, health = collect_github_releases([source], session=Session(), now=now)
    selected, _ = select_editorial_events(events, now=now)
    assert health == {"github:github/copilot-cli": "ok:2"}
    assert len(selected) == 1
    assert selected[0].product == "GitHub Copilot CLI"
    assert selected[0].url.endswith("v1.0.90")
    assert not select_editorial_events(events, [selected[0].event_id], now=now)[0]
