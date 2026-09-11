"""Static workflow contracts. Never dispatch or execute publishing shell steps."""
import ast
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"


def workflow(name):
    # YAML 1.1 safe_load interprets the Actions `on` key as boolean True.
    return yaml.load((WORKFLOWS / name).read_text(), Loader=yaml.BaseLoader)


def steps(name):
    return [step for job in workflow(name)["jobs"].values() for step in job.get("steps", [])]


@pytest.mark.parametrize("name", ["pages.yml", "update-radar.yml", "youtube-trends.yml"])
def test_publishers_share_non_cancelling_concurrency(name):
    assert workflow(name)["concurrency"] == {"group": "podcast-publisher", "cancel-in-progress": "false"}


def test_pages_retains_push_and_manual_recovery():
    document = workflow("pages.yml")
    assert "workflow_dispatch" in document["on"]
    assert document["on"]["push"]["branches"] == ["main"]
    assert "podcast.xml" in document["on"]["push"]["paths"]
    assert any(step.get("uses") == "actions/deploy-pages@v4" for step in steps("pages.yml"))
    # The daily publisher deploys inline: waiting on a separately locked workflow deadlocks.
    assert any(step.get("uses") == "actions/deploy-pages@v4" for step in steps("update-radar.yml"))


def test_delivery_workflow_binds_candidate_and_downloaded_release():
    by_name = {step.get("name"): step for step in steps("update-radar.yml")}
    finalize = by_name["Verify audio and build candidate feed"]["run"]
    assert "--publication .cache/publication.json" in finalize
    delivery = by_name["Verify subscriber-facing delivery"]
    assert '--candidate "data/episodes/${EXPECTED_GUID}.json"' in delivery["run"]
    assert delivery["env"]["EXPECTED_GUID"] == "${{ steps.prepare.outputs.episode_id }}"
    assert "--retries 10" in delivery["run"]
    assert "--skip-remote-verification" not in finalize
    upload = by_name["Upload or resume immutable release assets"]["run"]
    assert "gh release download" in upload
    assert "--pattern episode-manifest.json" in upload
    assert "--pattern daily-ai-brief.mp3" in upload


def test_independent_monitor_remains_age_sensitive():
    monitor = next(step["run"] for step in steps("feed-health.yml") if step.get("name") == "Verify public feed freshness")
    assert "--max-age-hours 25" in monitor
    assert "--candidate" not in monitor


def test_youtube_diagnostics_are_always_retained_without_transcripts():
    upload = next(step for step in steps("youtube-trends.yml") if step.get("uses") == "actions/upload-artifact@v4")
    assert upload["if"] == "always()"
    assert upload["with"]["path"] == ".cache/youtube-discovery-health.json"
    assert upload["with"]["retention-days"] == "14"
    discover = next(step for step in steps("youtube-trends.yml") if step.get("name", "").startswith("Discover"))
    assert discover.get("continue-on-error", "false") == "false"


@pytest.mark.parametrize("status,passes", [("ok:0", True), ("ok:1", True), ("degraded:0", False),
                                           ("degraded:1", False), ("error:missing", False)])
def test_actual_weekly_validation_assertion_rejects_degraded_status(monkeypatch, status, passes):
    command = next(step["run"] for step in steps("youtube-trends.yml")
                   if step.get("name") == "Validate the digest through the daily source adapter")
    args = shlex.split(command)
    assert args[:2] == ["python", "-c"]
    program = compile(ast.parse(args[2]), "weekly-workflow-validation", "exec")
    events = [object()] if status.endswith(":1") else []
    def adapter(config):
        assert config["required"] is True
        return events, {"youtube:weekly-digest": status}
    monkeypatch.setattr("pipeline.sources.youtube.collect_youtube_digest", adapter)
    if passes:
        exec(program, {})
    else:
        with pytest.raises(AssertionError):
            exec(program, {})


@pytest.mark.parametrize("path", sorted(WORKFLOWS.glob("*.yml")), ids=lambda path: path.name)
def test_workflow_yaml_and_shell_syntax_without_execution(path):
    document = workflow(path.name)
    assert document["name"] and document["on"] and document["jobs"]
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash is not installed")
    for step in steps(path.name):
        if "run" in step:
            result = subprocess.run([bash, "-n"], input=step["run"], text=True, capture_output=True)
            assert result.returncode == 0, f"{path.name}: {result.stderr}"
