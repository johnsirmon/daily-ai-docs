from types import SimpleNamespace
from typing import cast

import pytest

from pipeline.schema import EpisodeManifest
from pipeline.usefulness import (
    PublicationUsefulnessError,
    publication_usefulness_findings,
    validate_publication_usefulness,
)


def _manifest(narration: str, *, schema_version: int = 1, actions=(), verified=False):
    return cast(EpisodeManifest, SimpleNamespace(
        narration=narration,
        schema_version=schema_version,
        generation={"verified": verified},
        stories=[SimpleNamespace(action=action, kind="product") for action in actions],
    ))


def test_rejects_recent_release_fragment_shape_and_generic_filler():
    manifest = _manifest(
        "(#48151) Bug Fixes. Windows launches avoid stray console windows. "
        "No additional workflow change is supported beyond the cited evidence."
    )
    findings = publication_usefulness_findings(manifest)
    assert "pull-request or issue identifier" in " ".join(findings)
    assert "generic no-value workflow filler" in findings
    with pytest.raises(PublicationUsefulnessError):
        validate_publication_usefulness(manifest)


@pytest.mark.parametrize("text", [
    "The change in PR #48151 adds sandboxed command previews.",
    "The change in #48151 adds sandboxed command previews.",
    "Pull-request 48151 adds sandboxed command previews.",
    "Issue #7 adds sandboxed command previews.",
    "Commit 225be55 adds sandboxed command previews.",
    "Commit 225be554c1b adds sandboxed command previews.",
    "No workflow change is supported beyond the cited evidence.",
])
def test_rejects_common_repository_fragments(text):
    manifest = _manifest(text, schema_version=2, actions=("skip",), verified=True)
    assert publication_usefulness_findings(manifest)


@pytest.mark.parametrize("text", [
    "The API returns HTTP 403 when enrichment is unavailable.",
    "Version 6.1 costs less for this documented input tier.",
    "Run 7 representative tasks before changing the default.",
])
def test_admits_useful_contextual_numbers(text):
    manifest = _manifest(text, schema_version=2, actions=("skip",), verified=True)
    assert publication_usefulness_findings(manifest) == []


def test_rejects_spoken_markdown_urls_and_hashes():
    manifest = _manifest(
        "# Update\nRead [the notes](https://example.com) at `abcdef0123456789`."
    )
    findings = " ".join(publication_usefulness_findings(manifest))
    assert "Markdown heading" in findings
    assert "raw URL" in findings
    assert "commit hash" in findings


def test_verified_useful_brief_with_skip_takeaway_is_admitted():
    manifest = _manifest(
        "The practical change today is that teams can test the managed agent path without "
        "rebuilding their own harness. Start with a bounded internal workflow, retain your "
        "existing authorization controls, and compare cost before moving a production job. "
        "Skip migration if your current harness already meets the documented requirement.",
        schema_version=2,
        actions=("act", "watch", "skip"),
        verified=True,
    )
    assert publication_usefulness_findings(manifest) == []
    validate_publication_usefulness(manifest)


def test_grounded_editorial_requires_verification_and_not_worth_chasing_takeaway():
    manifest = _manifest(
        "A concrete developer briefing with supported consequences and a useful next step.",
        schema_version=2,
        actions=("act", "watch"),
        verified=False,
    )
    findings = publication_usefulness_findings(manifest)
    assert "grounded editorial script lacks independent model verification" in findings
    assert "briefing does not identify anything that is not worth chasing" in findings


def test_fresh_deterministic_brief_cannot_satisfy_usefulness_policy():
    findings = publication_usefulness_findings(_manifest(
        "A concrete developer briefing with a bounded experiment and a clear skip decision."
    ))
    assert "fresh briefing is not grounded independently verified editorial" in findings
