"""Tests for config-to-README drift validation."""

from pathlib import Path

from pipeline.drift_check import validate_readme_drift
from pipeline.render import render_readme


def _config_text() -> str:
    return (
        "settings: {}\n"
        "topics:\n"
        "  - id: github-copilot\n"
        '    display: "GitHub Copilot"\n'
        "  - id: mcp\n"
        '    display: "MCP Ecosystem"\n'
    )


def _topic(tid: str, display: str) -> dict:
    return {
        "id": tid,
        "display": display,
        "items": [],
        "why": "",
        "learn": "",
        "summary": "",
        "community_pulse": "",
        "action_items": [],
        "deep_dives": [],
    }


def _write_inputs(tmp_path: Path, readme_text: str) -> tuple[Path, Path]:
    config_path = tmp_path / "topics.yaml"
    readme_path = tmp_path / "README.md"
    config_path.write_text(_config_text(), encoding="utf-8")
    readme_path.write_text(readme_text, encoding="utf-8")
    return config_path, readme_path


def test_validate_readme_drift_passes_for_rendered_readme(tmp_path):
    readme = render_readme([
        _topic("github-copilot", "GitHub Copilot"),
        _topic("mcp", "MCP Ecosystem"),
    ])
    config_path, readme_path = _write_inputs(tmp_path, readme)

    assert validate_readme_drift(config_path, readme_path) == []


def test_validate_readme_drift_reports_missing_topic_list_entry(tmp_path):
    readme = render_readme([
        _topic("github-copilot", "GitHub Copilot"),
        _topic("mcp", "MCP Ecosystem"),
    ]).replace("- [MCP Ecosystem](#mcp)\n", "")
    config_path, readme_path = _write_inputs(tmp_path, readme)

    errors = validate_readme_drift(config_path, readme_path)
    assert "Missing README topic list entry for 'MCP Ecosystem' (#mcp)." in errors


def test_validate_readme_drift_reports_missing_explicit_anchor(tmp_path):
    readme = render_readme([
        _topic("github-copilot", "GitHub Copilot"),
        _topic("mcp", "MCP Ecosystem"),
    ]).replace('<a id="mcp"></a>\n', "")
    config_path, readme_path = _write_inputs(tmp_path, readme)

    errors = validate_readme_drift(config_path, readme_path)
    assert "Missing explicit README anchor for 'MCP Ecosystem' (#mcp)." in errors


def test_validate_readme_drift_reports_heading_alignment_drift(tmp_path):
    readme = render_readme([
        _topic("github-copilot", "GitHub Copilot"),
        _topic("mcp", "MCP Ecosystem"),
    ]).replace("## MCP Ecosystem", "## MCP Changed")
    config_path, readme_path = _write_inputs(tmp_path, readme)

    errors = validate_readme_drift(config_path, readme_path)
    assert "Missing README section heading for 'MCP Ecosystem' (#mcp)." in errors