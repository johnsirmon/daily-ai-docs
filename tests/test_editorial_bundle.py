import json
import pytest
from pipeline.editorial_bundle import load_bundle


def packet():
    return {"schema_version": 1, "bundle_id": "public-2026-10-01", "generated_at": "2026-10-01T12:00:00Z", "items": [{
        "id": "mcp-recovery", "published_at": "2026-10-01T10:00:00Z", "canonical_url": "https://sirmon.ai/notes/mcp-recovery",
        "title": "MCP recovery", "narration_summary": "Tools can recover.", "why_it_matters": "Inspect discovery recovery.",
        "affected_workflow": "MCP discovery", "decision": "try", "experiment": "Try a read-only test.", "caveat": "Not a measured gain.",
        "claims": [{"text": "Tools can recover.", "source_url": "https://github.com/github/copilot-cli/releases/tag/v1.0.90",
                    "quote": "MCP tools recover after transient discovery failures.", "source_published_at": "2026-09-30T21:38:30Z"}]}]}


def test_consumes_one_public_handoff_without_promoting_it_to_verified(tmp_path):
    file = tmp_path / "research.json"
    file.write_text(json.dumps(packet()))
    result = load_bundle(file)
    assert result["items"][0]["id"] == "mcp-recovery"
    assert result["purpose"] == "untrusted_drafting_context"
    assert result["publication_approved"] is False
    assert load_bundle(file, seen_item_ids=["mcp-recovery"])["items"] == []


@pytest.mark.parametrize("change", [
    lambda p: p.update(private_notes="not public"),
    lambda p: p["items"][0].update(employer="private"),
    lambda p: p["items"][0].update(claims=[]),
    lambda p: p["items"][0]["claims"][0].update(source_url="http://127.0.0.1/private"),
    lambda p: p["items"][0]["claims"][0].update(source_url=p["items"][0]["canonical_url"]),
    lambda p: p["items"].append(p["items"][0]),
    lambda p: p["items"][0].update(published_at="2027-01-01T00:00:00Z"),
    lambda p: p.update(schema_version=True),
])
def test_rejects_private_unsupported_or_ambiguous_bundle(change, tmp_path):
    data = packet(); change(data)
    file = tmp_path / "research.json"; file.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_bundle(file)
