"""Static workflow contracts. Never dispatch or execute publishing shell steps."""
import ast
import re
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"
FULL_ACTION_SHA = re.compile(r"^[0-9a-f]{40}$")


def workflow(name):
    # YAML 1.1 safe_load interprets the Actions `on` key as boolean True.
    return yaml.load((WORKFLOWS / name).read_text(), Loader=yaml.BaseLoader)


def steps(name):
    return [step for job in workflow(name)["jobs"].values() for step in job.get("steps", [])]


def action_name(reference):
    return reference.partition("@")[0]


def third_party_action_is_pinned(reference):
    if reference.startswith("./"):
        return True
    _, separator, revision = reference.rpartition("@")
    return bool(separator and FULL_ACTION_SHA.fullmatch(revision))


def test_all_third_party_actions_use_full_commit_shas():
    fixture = yaml.load(
        "jobs:\n  test:\n    steps:\n      - uses: owner/action@v1\n",
        Loader=yaml.BaseLoader,
    )
    reference = fixture["jobs"]["test"]["steps"][0]["uses"]
    assert not third_party_action_is_pinned(reference)
    assert third_party_action_is_pinned("owner/action@0123456789abcdef0123456789abcdef01234567")

    mutable = {
        f"{path.name}: {step['uses']}"
        for path in WORKFLOWS.glob("*.yml")
        for step in steps(path.name)
        if "uses" in step and not third_party_action_is_pinned(step["uses"])
    }
    assert not mutable, "Mutable action references:\n" + "\n".join(sorted(mutable))


def test_daily_publisher_has_memorable_actions_name():
    assert workflow("update-radar.yml")["name"] == "Publish Daily AI Developer Brief"


@pytest.mark.parametrize("name", ["pages.yml", "update-radar.yml", "youtube-trends.yml"])
def test_publishers_share_non_cancelling_concurrency(name):
    assert workflow(name)["concurrency"] == {"group": "podcast-publisher", "cancel-in-progress": "false"}


@pytest.mark.parametrize("name", ["pages.yml", "update-radar.yml", "youtube-trends.yml"])
def test_publishers_always_operate_from_current_main(name):
    checkout = next(step for step in steps(name) if action_name(step.get("uses", "")) == "actions/checkout")
    assert checkout["with"]["ref"] == "main"


def test_pages_retains_push_and_manual_recovery():
    document = workflow("pages.yml")
    assert "workflow_dispatch" in document["on"]
    assert document["on"]["push"]["branches"] == ["main"]
    assert "podcast.xml" in document["on"]["push"]["paths"]
    assert any(action_name(step.get("uses", "")) == "actions/deploy-pages" for step in steps("pages.yml"))
    # The daily publisher deploys inline: waiting on a separately locked workflow deadlocks.
    assert any(action_name(step.get("uses", "")) == "actions/deploy-pages" for step in steps("update-radar.yml"))


@pytest.mark.parametrize("name", ["pages.yml", "update-radar.yml"])
def test_pages_deploys_versioned_and_previous_show_artwork(name):
    runs = "\n".join(step.get("run", "") for step in steps(name))
    assert "cp assets/podcast-cover*.jpg _site/assets/" in runs
    assert "assets/podcast-cover*.jpg" in workflow("pages.yml")["on"]["push"]["paths"]


@pytest.mark.parametrize("name", ["pages.yml", "update-radar.yml"])
def test_pages_retains_only_public_episode_jpegs(name):
    runs = "\n".join(step.get("run", "") for step in steps(name))
    assert "mkdir -p _site/assets/episodes" in runs
    assert 'for image in assets/episodes/*.jpg; do' in runs
    assert '[ -f "$image" ] || continue' in runs
    assert 'cp "$image" _site/assets/episodes/' in runs
    assert "assets/episodes/*.jpg" in workflow("pages.yml")["on"]["push"]["paths"]
    assert "cp -r assets" not in runs


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
    install = by_name["Install dependencies and media tools"]["run"]
    assert "command -v ffmpeg" in install and "command -v ffprobe" in install


def test_scheduled_audio_polish_is_explicit_and_defaults_off():
    environment = workflow("update-radar.yml")["env"]
    assert environment["PODCAST_AUDIO_POLISH"] == "${{ vars.PODCAST_AUDIO_POLISH || '0' }}"


def test_reviewed_release_uses_existing_locked_publisher_without_regeneration():
    document = workflow("update-radar.yml")
    assert document["jobs"]["publish"]["if"] == "github.ref == 'refs/heads/main'"
    assert document["on"]["workflow_dispatch"]["inputs"]["reviewed_episode"]["default"] == ""
    prepare = next(step for step in steps("update-radar.yml")
                   if step.get("name") == "Prepare evidence, narration, and validated audio")
    assert prepare["env"]["REVIEWED_EPISODE"] == "${{ inputs.reviewed_episode }}"
    reviewed_branch = prepare["run"].split("\nelse\n")[0]
    assert "resume-reviewed" in reviewed_branch
    assert "gh release download" in reviewed_branch
    assert "--json isDraft,isPrerelease" in reviewed_branch
    assert "grep -qx true" in reviewed_branch
    assert "--clobber" not in reviewed_branch
    assert "daily prepare" not in reviewed_branch
    assert "${{ inputs.reviewed_episode }}" not in prepare["run"]
    assert "^daily-" in reviewed_branch
    upload = next(step for step in steps("update-radar.yml")
                  if step.get("name") == "Upload or resume immutable release assets")
    assert upload["env"]["REVIEWED_EPISODE"] == "${{ inputs.reviewed_episode }}"
    assert "test -s .cache/daily-ai-brief.mp3" in upload["run"]


def test_independent_monitor_remains_age_sensitive():
    monitor = next(step["run"] for step in steps("feed-health.yml") if step.get("name") == "Verify public feed freshness")
    assert "--max-age-hours 25" in monitor
    assert "--candidate" not in monitor
    assert "--allow-editorial-skips" in monitor


@pytest.mark.parametrize(("name", "cron", "documented_time"), [
    ("update-radar.yml", "17 10 * * *", "Daily **10:17 UTC** (06:17 EDT / 05:17 EST)"),
    ("feed-health.yml", "47 12 * * *", "Daily **12:47 UTC** (08:47 EDT / 07:47 EST)"),
    ("youtube-trends.yml", "23 11 * * 0", "Sunday **11:23 UTC** (07:23 EDT / 06:23 EST)"),
])
def test_readme_schedule_table_matches_workflow(name, cron, documented_time):
    from pipeline.render import render_manifest_readme
    from pipeline.schema import EpisodeManifest

    manifest = EpisodeManifest(
        1, "daily-test", "2026-09-07T12:00:00Z", "draft",
        {"github:tool": "ok:0"}, [], [], [],
        "A quiet daily brief with enough words to validate.", "No updates.",
        {"edition": "quiet"}, {},
    )
    assert workflow(name)["on"]["schedule"] == [{"cron": cron}]
    for readme in (render_manifest_readme(manifest), (ROOT / "README.md").read_text(encoding="utf-8")):
        row = next(line for line in readme.splitlines() if f"](.github/workflows/{name})" in line)
        assert documented_time in row


def test_adhoc_intake_cannot_publish_or_execute_issue_body():
    document = workflow("adhoc-podcast.yml")
    assert document["permissions"]["contents"] == "read"
    assert document["concurrency"]["group"] != "podcast-publisher"
    runs = "\n".join(step.get("run", "") for step in steps("adhoc-podcast.yml"))
    assert "pipeline.adhoc issue" in runs
    assert "issue.body" not in runs
    assert "gh release" not in runs and "pipeline.daily" not in runs
    assert "workflow" not in runs


def test_adhoc_bundle_authorized_before_locked_promotion():
    all_steps = steps("update-radar.yml")
    prepare = next(step["run"] for step in all_steps if step.get("id") == "prepare")
    assert "pipeline.adhoc verify --directory .cache" in prepare
    upload = next(step["run"] for step in all_steps
                  if step.get("name") == "Upload or resume immutable release assets")
    assert '--draft=false' in upload
    failure = next(step for step in all_steps if step.get("name") == "Persist failed editorial run")
    assert "!startsWith(inputs.reviewed_episode, 'adhoc-')" in failure["if"]


def test_skip_guards_every_publication_step_and_persists_receipt():
    all_steps = steps("update-radar.yml")
    first = next(index for index, step in enumerate(all_steps)
                 if step.get("name") == "Upload or resume immutable release assets")
    last = next(index for index, step in enumerate(all_steps)
                if step.get("name") == "Commit publication receipt and state")
    for step in all_steps[first:last + 1]:
        assert step.get("if") == "steps.prepare.outputs.outcome == 'publish'"
    skipped = next(step for step in all_steps if step.get("name") == "Persist skip receipt")
    assert skipped["if"] == "steps.prepare.outputs.outcome == 'skipped'"
    assert "data/runs/latest.json" in skipped["run"]
    failed = next(step for step in all_steps if step.get("name") == "Persist failed editorial run")
    assert "failure()" in failed["if"] and "fail-run" in failed["run"]


def test_preview_cannot_publish_and_requires_an_explicit_trigger():
    document = workflow("editorial-preview.yml")
    assert document["permissions"] == {"contents": "read"}
    assert document["on"]["push"]["branches"] == ["feature/grounded-daily-ai-brief"]
    assert "schedule" not in document["on"]
    assert "[editorial-preview]" in document["jobs"]["preview"]["if"]
    all_steps = steps("editorial-preview.yml")
    history = next(step for step in all_steps if step.get("name") == "Load current public publication history")
    assert history["with"]["ref"] == "main"
    assert history["with"]["sparse-checkout"] == "data"
    prepare = next(step for step in all_steps if step.get("name") == "Prepare one unpublished preview")
    assert "pipeline.preview" in prepare["run"]
    assert "--history-root .preview-history --free-tier-confirmed" in prepare["run"]
    assert prepare["env"]["TTS_PROVIDER"] == "edge"
    assert prepare["env"]["AI_EDITORIAL"] == "required"
    commands = "\n".join(step.get("run", "") for step in all_steps)
    assert not any(command in commands for command in
                   ("git push", "git commit", "gh release", "pipeline.daily finalize", "pipeline.daily confirm"))
    assert not any("pages" in step.get("uses", "") for step in all_steps)
    upload = next(step for step in all_steps
                  if action_name(step.get("uses", "")) == "actions/upload-artifact")
    assert upload["if"] == "always()"
    assert ".cache/publication.json" not in upload["with"]["path"]


def test_youtube_diagnostics_are_always_retained_without_transcripts():
    upload = next(step for step in steps("youtube-trends.yml")
                  if action_name(step.get("uses", "")) == "actions/upload-artifact")
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
            result = subprocess.run([bash, "-n"], input=step["run"].encode("utf-8"), capture_output=True)
            assert result.returncode == 0, f"{path.name}: {result.stderr}"
