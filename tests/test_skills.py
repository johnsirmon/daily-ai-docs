"""Offline operating-skill contracts; never execute generation or publication."""

import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from urllib.parse import unquote, urlsplit

import pytest
import yaml

from pipeline.schema import EpisodeManifest, SchemaError
from tests.test_adhoc import long_draft


ROOT = Path(__file__).resolve().parents[1]
SKILLS = sorted((ROOT / ".agents" / "skills").glob("*/SKILL.md"))
DOCUMENTS = SKILLS + [
    ROOT / ".github" / "copilot-instructions.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "docs" / "OPERATIONS.md",
    ROOT / "docs" / "SESSION_LESSONS.md",
]
AUDIO_SKILL = ROOT / ".agents" / "skills" / "audio-production-review" / "SKILL.md"
HELP_COMMANDS = {
    "pipeline.adhoc": {
        "request", "issue", "brief", "prepare", "publish", "status", "verify", "papers", "synthesize",
    },
    "pipeline.reviewed_audio": {""},
}


def _metadata(text: str) -> dict:
    match = re.match(r"\A---\n(.*?)\n---(?:\n|$)", text, re.DOTALL)
    assert match, "skill requires YAML frontmatter"
    metadata = yaml.safe_load(match[1])
    assert isinstance(metadata, dict), "frontmatter must be an object"
    for key in ("name", "description"):
        assert isinstance(metadata.get(key), str) and metadata[key].strip(), f"missing {key}"
    assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", metadata["name"]), "invalid skill name"
    if "triggers" in metadata:
        triggers = metadata["triggers"]
        assert isinstance(triggers, list) and triggers, "triggers must be a non-empty list"
        assert all(isinstance(value, str) and value.strip() for value in triggers), "invalid trigger"
    return metadata


def _check_links(document: Path) -> None:
    for target in re.findall(r"\[[^\]]+\]\(([^)\s]+)\)", document.read_text(encoding="utf-8")):
        url = urlsplit(target)
        if url.scheme or url.netloc or not url.path:
            continue
        path = document.parent / unquote(url.path)
        assert path.exists(), f"{document}: missing local link target {target}"


def _check_test_references(text: str, root: Path = ROOT) -> None:
    references = re.findall(r"\btests[/\\](test_[a-z0-9_]+\.py)\b|`(test_[a-z0-9_]+)`", text)
    for filename, short_name in references:
        path = root / "tests" / (filename or f"{short_name}.py")
        assert path.is_file(), f"missing referenced test file: {path}"


def _help_examples(document: Path) -> list[str]:
    examples = []
    for block in re.findall(r"```(?:sh|bash|powershell)\n(.*?)\n```",
                            document.read_text(encoding="utf-8"), re.DOTALL):
        examples.extend(line.strip() for line in block.splitlines() if "--help" in line)
    return examples


def _help_arguments(command: str) -> list[str]:
    args = shlex.split(command)
    assert len(args) in {4, 5}, "help example must be a single bounded command"
    assert args[:2] == ["python", "-m"] and args[-1] == "--help", "only help may execute"
    module = args[2]
    assert module in HELP_COMMANDS, "module is not approved for offline help"
    subcommand = args[3] if len(args) == 5 else ""
    assert subcommand in HELP_COMMANDS[module], "subcommand is not approved for offline help"
    return args[1:]


def test_skill_catalog_has_unique_discoverable_names():
    assert SKILLS, "no repository skills found"
    names = [_metadata(path.read_text(encoding="utf-8"))["name"] for path in SKILLS]
    assert len(names) == len(set(names))
    assert names == [path.parent.name for path in SKILLS]


@pytest.mark.parametrize("document", DOCUMENTS, ids=lambda path: path.relative_to(ROOT).as_posix())
def test_operating_document_local_links_exist(document):
    _check_links(document)


@pytest.mark.parametrize("document", DOCUMENTS, ids=lambda path: path.relative_to(ROOT).as_posix())
def test_operating_document_test_references_exist(document):
    _check_test_references(document.read_text(encoding="utf-8"))


@pytest.mark.parametrize("text", [
    "# No metadata",
    "---\nname: invalid_name\ndescription: Test\n---\n",
    "---\nname: valid-name\ndescription: ''\n---\n",
    "---\nname: valid-name\ndescription: Test\ntriggers: not-a-list\n---\n",
])
def test_metadata_check_rejects_invalid_skills(text):
    with pytest.raises(AssertionError):
        _metadata(text)


def test_link_check_rejects_missing_local_file_but_ignores_external_links(tmp_path):
    document = tmp_path / "SKILL.md"
    document.write_text("[Web](https://example.com/ignored) [Section](#section)", encoding="utf-8")
    _check_links(document)
    document.write_text("[Missing](missing.md#section)", encoding="utf-8")
    with pytest.raises(AssertionError, match="missing local link"):
        _check_links(document)


@pytest.mark.parametrize("reference", ["tests/test_missing.py", "`test_missing`"])
def test_test_reference_check_rejects_missing_files(tmp_path, reference):
    with pytest.raises(AssertionError, match="missing referenced test"):
        _check_test_references(reference, tmp_path)


@pytest.mark.parametrize("command", [
    "python -m pipeline.adhoc publish",
    "python -m pipeline.adhoc publish --help; gh release create",
    "python -m pipeline.daily prepare --help",
    "python -m pipeline.adhoc unknown --help",
])
def test_help_check_rejects_unapproved_or_side_effecting_commands(command):
    with pytest.raises(AssertionError):
        _help_arguments(command)


def test_documented_cli_help_is_current_and_writes_no_staging(tmp_path):
    examples = [command for skill in SKILLS for command in _help_examples(skill)]
    assert examples, "no help-only discovery examples found"
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
    for command in dict.fromkeys(examples):
        result = subprocess.run(
            [sys.executable, *_help_arguments(command)],
            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"{command}: {result.stderr}"
        assert "usage:" in result.stdout, f"{command}: help output missing"
    assert not list(tmp_path.iterdir()), "help created files in the working directory"


def _example_manifest() -> dict:
    blocks = re.findall(r"```json\n(.*?)\n```", AUDIO_SKILL.read_text(encoding="utf-8"), re.DOTALL)
    assert len(blocks) == 1, "expected one illustrative review packet"
    review = json.loads(blocks[0])
    assert set(review) == {"transcript", "review", "voice"}
    assert set(review["transcript"]) == {"engine", "model"}
    data = long_draft()
    data["generation"].update(review)
    data["generation"]["transcript"]["sha256"] = hashlib.sha256(data["narration"].encode("utf-8")).hexdigest()
    return data


def test_audio_review_example_matches_draft_contract_not_publication():
    manifest = EpisodeManifest.from_dict(_example_manifest())
    assert manifest.status == "draft"
    assert manifest.generation["request"]["publish_now"] is False
    assert manifest.generation["quality"] == {}
    assert manifest.generation["voice"] == {}
    with pytest.raises(SchemaError):
        manifest.validate(require_audio=True)


@pytest.mark.parametrize("field", ["text", "quote", "event_id"])
def test_audio_review_example_rejects_unbound_claims(field):
    data = _example_manifest()
    data["generation"]["review"]["claims"][0][field] = "not-in-the-fixture"
    with pytest.raises(SchemaError):
        EpisodeManifest.from_dict(data)
