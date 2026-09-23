"""Local browser UI for listening to and approving an unpublished episode."""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
import webbrowser

from .audio import file_sha256
from .schema import EpisodeManifest

APPROVAL_FILE = "listening-approval.json"
PUBLICATION_AUTHORIZATION_FILE = "publication-authorization.json"
PUBLICATION_QUEUE_FILE = "publication-queue.json"
REQUIRED_CHECKS = {
    "disclosure",
    "first_useful_point",
    "claims",
    "pronunciation",
    "pacing",
    "takeaways",
    "transcript",
}


@dataclass(frozen=True)
class ReviewBundle:
    directory: Path
    manifest: EpisodeManifest
    audio_path: Path
    transcript: str
    show_notes: str
    manifest_sha256: str
    transcript_sha256: str

    @property
    def approval_path(self) -> Path:
        return self.directory / APPROVAL_FILE


def load_review_bundle(directory: Path) -> ReviewBundle:
    directory = directory.resolve()
    manifest_path = directory / "episode-manifest.json"
    audio_path = directory / "daily-ai-brief.mp3"
    if not manifest_path.is_file() or not audio_path.is_file():
        raise FileNotFoundError("review directory requires episode-manifest.json and daily-ai-brief.mp3")
    manifest_bytes = manifest_path.read_bytes()
    manifest = EpisodeManifest.from_dict(json.loads(manifest_bytes.decode("utf-8")))
    if manifest.status != "ready":
        raise ValueError("review UI accepts only an unpublished ready manifest")
    manifest.validate(require_audio=True)
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    if manifest.generation.get("edition") == "gate-a-one-release-waiver":
        from .gate_a_release import validate_exact_publication_manifest
        validate_exact_publication_manifest(manifest, manifest_sha256=manifest_sha256)
    if audio_path.stat().st_size != int(manifest.audio["size_bytes"]):
        raise ValueError("review audio byte length does not match the manifest")
    if file_sha256(audio_path) != manifest.audio["sha256"]:
        raise ValueError("review audio SHA-256 does not match the manifest")

    transcript_path = directory / "narration.txt"
    if transcript_path.exists():
        transcript = transcript_path.read_text(encoding="utf-8")
        if transcript.endswith("\n"):
            transcript = transcript[:-1]
    else:
        transcript = manifest.narration
    if transcript != manifest.narration:
        raise ValueError("review transcript does not exactly match manifest narration")
    show_notes_path = directory / "show-notes.txt"
    show_notes = (
        show_notes_path.read_text(encoding="utf-8")
        if show_notes_path.exists() else manifest.show_notes
    )
    return ReviewBundle(
        directory=directory,
        manifest=manifest,
        audio_path=audio_path,
        transcript=transcript,
        show_notes=show_notes,
        manifest_sha256=manifest_sha256,
        transcript_sha256=hashlib.sha256(transcript.encode("utf-8")).hexdigest(),
    )


def _publication_reason(bundle: ReviewBundle, allow_publish: bool) -> str:
    if bundle.manifest.generation.get("preview_only") is True:
        return "Preview-only bundles cannot be published."
    if bundle.manifest.schema_version not in {3, 4}:
        return "Only reviewed schema-3 or schema-4 bundles can use UI publication."
    if not allow_publish:
        return "Restart this UI with --allow-publish to expose the publication action."
    return ""


def review_payload(bundle: ReviewBundle, *, allow_publish: bool = False) -> dict[str, Any]:
    events = {event.event_id: event for event in bundle.manifest.source_events}
    stories = []
    for story in bundle.manifest.stories:
        claims = story.editorial.get("claims", [])
        stories.append({
            "headline": story.headline,
            "what_changed": story.what_changed,
            "why_it_matters": story.why_it_matters,
            "action": story.action,
            "rationale": story.rationale,
            "claims": [{
                "text": claim["text"],
                "event_id": claim["event_id"],
                "quote": claim["quote"],
                "url": events[claim["event_id"]].url,
            } for claim in claims],
        })
    return {
        "episode_id": bundle.manifest.episode_id,
        "duration_secs": float(bundle.manifest.audio["duration_secs"]),
        "audio_sha256": bundle.manifest.audio["sha256"],
        "manifest_sha256": bundle.manifest_sha256,
        "transcript_sha256": bundle.transcript_sha256,
        "transcript": bundle.transcript,
        "show_notes": bundle.show_notes,
        "stories": stories,
        "already_approved": bundle.approval_path.exists(),
        "publish_allowed": not _publication_reason(bundle, allow_publish),
        "publish_reason": _publication_reason(bundle, allow_publish),
        "publication_queued": (bundle.directory / PUBLICATION_QUEUE_FILE).exists(),
    }


def record_approval(bundle: ReviewBundle, submission: dict[str, Any]) -> dict[str, Any]:
    if bundle.approval_path.exists():
        raise FileExistsError("this exact review bundle already has a listening approval")
    reviewer = submission.get("reviewer")
    if not isinstance(reviewer, str) or not 2 <= len(reviewer.strip()) <= 100:
        raise ValueError("reviewer name is required")
    checks = submission.get("checks")
    if not isinstance(checks, dict) or set(checks) != REQUIRED_CHECKS or not all(
        value is True for value in checks.values()
    ):
        raise ValueError("every listening and claim-review check must be accepted")
    if submission.get("playback_complete") is not True:
        raise ValueError("complete playback is required")
    listened_seconds = submission.get("listened_seconds")
    if type(listened_seconds) not in {int, float}:
        raise ValueError("measured listening coverage is required")
    duration = float(bundle.manifest.audio["duration_secs"])
    if not 0.98 * duration <= float(listened_seconds) <= duration + 1:
        raise ValueError("at least 98% measured playback coverage is required")
    notes = submission.get("notes", "")
    if not isinstance(notes, str) or len(notes) > 4000:
        raise ValueError("review notes must be text no longer than 4000 characters")

    approval = {
        "schema_version": 1,
        "purpose": "unpublished_listening_approval",
        "decision": "approved",
        "episode_id": bundle.manifest.episode_id,
        "approved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "reviewer": reviewer.strip(),
        "audio_sha256": bundle.manifest.audio["sha256"],
        "manifest_sha256": bundle.manifest_sha256,
        "transcript_sha256": bundle.transcript_sha256,
        "duration_secs": duration,
        "listened_seconds": round(float(listened_seconds), 3),
        "coverage_percent": round(min(100.0, 100 * float(listened_seconds) / duration), 2),
        "checks": checks,
        "notes": notes.strip(),
        "publication_authorized": False,
    }
    with bundle.approval_path.open("x", encoding="utf-8") as stream:
        json.dump(approval, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    return approval


def _load_approval(bundle: ReviewBundle) -> dict[str, Any]:
    if bundle.manifest.generation.get("edition") == "gate-a-one-release-waiver":
        from .gate_a_release import (
            AUDIO_SHA256,
            AUTHORIZED_MANIFEST_SHA256,
            AUTHORIZED_AT,
            EPISODE_ID,
            SCRIPT_SHA256,
            validate_exact_publication_manifest,
        )

        validate_exact_publication_manifest(
            bundle.manifest, manifest_sha256=bundle.manifest_sha256,
        )
        waiver_path = bundle.directory / "listening-waiver.json"
        if not waiver_path.is_file():
            raise ValueError("the exact Gate A board-approval substitution record is required")
        waiver = json.loads(waiver_path.read_text(encoding="utf-8"))
        expected = {
            "schema_version": 1,
            "purpose": "one_release_board_approval_substitution",
            "episode_id": EPISODE_ID,
            "authorized_at": AUTHORIZED_AT,
            "authorized_by": "John",
            "audio_sha256": AUDIO_SHA256,
            "manifest_sha256": AUTHORIZED_MANIFEST_SHA256,
            "script_sha256": SCRIPT_SHA256,
            "audible_disclosure": "waived_for_this_release_only",
            "publication_authorized": True,
        }
        if waiver != expected:
            raise ValueError("Gate A board-approval substitution does not match this exact bundle")
        return {
            "reviewer": "John",
            "decision": "approved_by_board_comment_substitution",
            "episode_id": EPISODE_ID,
            "audio_sha256": AUDIO_SHA256,
            "manifest_sha256": bundle.manifest_sha256,
            "transcript_sha256": bundle.transcript_sha256,
        }
    if not bundle.approval_path.is_file():
        raise ValueError("listening approval is required before publication")
    approval = json.loads(bundle.approval_path.read_text(encoding="utf-8"))
    expected = {
        "episode_id": bundle.manifest.episode_id,
        "audio_sha256": bundle.manifest.audio["sha256"],
        "manifest_sha256": bundle.manifest_sha256,
        "transcript_sha256": bundle.transcript_sha256,
    }
    if not isinstance(approval, dict) or any(approval.get(key) != value for key, value in expected.items()):
        raise ValueError("listening approval does not match the current bundle")
    checks = approval.get("checks")
    if (
        approval.get("decision") != "approved"
        or approval.get("publication_authorized") is not False
        or not isinstance(checks, dict)
        or set(checks) != REQUIRED_CHECKS
        or not all(value is True for value in checks.values())
        or float(approval.get("coverage_percent", 0)) < 98
    ):
        raise ValueError("listening approval is incomplete")
    return approval


def _run(command: list[str], *, timeout: int = 60) -> str:
    result = subprocess.run(
        command, check=False, capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise RuntimeError(detail[-1][:500] if detail else f"{command[0]} command failed")
    return result.stdout.strip()


def _repository() -> str:
    value = os.environ.get("GITHUB_REPOSITORY", "johnsirmon/daily-ai-docs")
    if value != "johnsirmon/daily-ai-docs":
        raise ValueError("review UI publication is restricted to the configured repository")
    return value


def _verify_publication_environment(repository: str) -> None:
    if not shutil.which("gh"):
        raise RuntimeError("GitHub CLI is required for publication")
    _run(["gh", "auth", "status"])
    if _run(["git", "branch", "--show-current"]) != "main":
        raise RuntimeError("publication requires the main branch")
    if _run(["git", "status", "--porcelain", "--untracked-files=no"]):
        raise RuntimeError("publication requires a clean tracked worktree")
    head = _run(["git", "rev-parse", "HEAD"])
    remote = _run(["gh", "api", f"repos/{repository}/commits/main", "--jq", ".sha"])
    if head != remote:
        raise RuntimeError("local HEAD must exactly match the current remote main commit")


def _release_matches(bundle: ReviewBundle, repository: str) -> bool:
    tag = bundle.manifest.episode_id
    result = subprocess.run(
        ["gh", "release", "view", tag, "--repo", repository, "--json", "isDraft,isPrerelease"],
        check=False, capture_output=True, text=True, timeout=60,
    )
    if result.returncode:
        return False
    state = json.loads(result.stdout)
    if state.get("isPrerelease") is True:
        raise RuntimeError("existing reviewed release must not be a prerelease")
    if bundle.manifest.schema_version == 3 and state.get("isDraft") is True:
        raise RuntimeError("existing schema-3 reviewed release must be public")
    with tempfile.TemporaryDirectory(prefix="daily-reviewed-release-") as directory:
        target = Path(directory)
        _run([
            "gh", "release", "download", tag, "--repo", repository,
            "--pattern", "daily-ai-brief.mp3", "--pattern", "episode-manifest.json",
            "--dir", str(target),
        ], timeout=180)
        if (
            (target / "daily-ai-brief.mp3").read_bytes() != bundle.audio_path.read_bytes()
            or (target / "episode-manifest.json").read_bytes()
            != (bundle.directory / "episode-manifest.json").read_bytes()
        ):
            raise RuntimeError("existing release assets do not exactly match the approved bundle")
    return True


def queue_publication(bundle: ReviewBundle, *, allow_publish: bool) -> dict[str, Any]:
    reason = _publication_reason(bundle, allow_publish)
    if reason:
        raise ValueError(reason)
    approval = _load_approval(bundle)
    queue_path = bundle.directory / PUBLICATION_QUEUE_FILE
    if queue_path.exists():
        queued = json.loads(queue_path.read_text(encoding="utf-8"))
        if (
            queued.get("episode_id") != bundle.manifest.episode_id
            or queued.get("audio_sha256") != bundle.manifest.audio["sha256"]
            or queued.get("manifest_sha256") != bundle.manifest_sha256
            or queued.get("transcript_sha256") != bundle.transcript_sha256
        ):
            raise ValueError("publication queue record does not match the current bundle")
        return queued

    authorization_path = bundle.directory / PUBLICATION_AUTHORIZATION_FILE
    authorization = {
        "schema_version": 1,
        "purpose": "reviewed_episode_publication_authorization",
        "episode_id": bundle.manifest.episode_id,
        "authorized_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "reviewer": approval["reviewer"],
        "audio_sha256": bundle.manifest.audio["sha256"],
        "manifest_sha256": bundle.manifest_sha256,
        "transcript_sha256": bundle.transcript_sha256,
    }
    if authorization_path.exists():
        if json.loads(authorization_path.read_text(encoding="utf-8")) != authorization:
            saved = json.loads(authorization_path.read_text(encoding="utf-8"))
            for key in authorization.keys() - {"authorized_at"}:
                if saved.get(key) != authorization[key]:
                    raise ValueError("publication authorization does not match the current bundle")
            authorization = saved
    else:
        with authorization_path.open("x", encoding="utf-8") as stream:
            json.dump(authorization, stream, indent=2, ensure_ascii=False)
            stream.write("\n")

    repository = _repository()
    _verify_publication_environment(repository)
    if bundle.manifest.schema_version == 4:
        from .adhoc import authorize
        from .podcast_request import PodcastRequest

        authorize(PodcastRequest.from_dict(bundle.manifest.generation["request"]), publishing=True)
    tag = bundle.manifest.episode_id
    if not _release_matches(bundle, repository):
        command = [
            "gh", "release", "create", tag,
            f"{bundle.audio_path}#daily-ai-brief.mp3",
            f"{bundle.directory / 'episode-manifest.json'}#episode-manifest.json",
            "--repo", repository,
            "--title", (
                f"Reviewed Daily AI Developer Brief {tag.removeprefix('daily-')}"
                if bundle.manifest.schema_version == 3
                else f"Special: {bundle.manifest.generation['request']['topic']}"
            ),
            "--notes", "Immutable reviewed audio and source-backed episode manifest.",
        ]
        if bundle.manifest.schema_version == 4:
            command.append("--draft")
        _run(command, timeout=180)
    _run([
        "gh", "workflow", "run", "update-radar.yml", "--repo", repository,
        "--ref", "main", "-f", f"reviewed_episode={tag}",
    ])
    queued = {
        "schema_version": 1,
        "status": "queued",
        "episode_id": tag,
        "queued_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "audio_sha256": bundle.manifest.audio["sha256"],
        "manifest_sha256": bundle.manifest_sha256,
        "transcript_sha256": bundle.transcript_sha256,
        "workflow": f"https://github.com/{repository}/actions/workflows/update-radar.yml",
        "subscriber_confirmed": False,
    }
    with queue_path.open("x", encoding="utf-8") as stream:
        json.dump(queued, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    return queued


def _page(payload: dict[str, Any], token: str) -> bytes:
    encoded = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Episode review</title>
<style>
:root {{ color-scheme: light; font-family: Inter, Segoe UI, sans-serif; background: #f3f5f7; color: #17212b; }}
body {{ margin: 0; }}
main {{ max-width: 1100px; margin: 0 auto; padding: 32px 20px 64px; }}
.hero {{ background: linear-gradient(135deg,#172554,#1d4ed8); color: white; padding: 28px; border-radius: 18px; }}
.eyebrow {{ text-transform: uppercase; letter-spacing: .12em; font-size: 12px; opacity: .8; }}
.grid {{ display: grid; grid-template-columns: minmax(0,1.15fr) minmax(320px,.85fr); gap: 20px; margin-top: 20px; }}
.card {{ background: white; border: 1px solid #dbe2ea; border-radius: 14px; padding: 20px; box-shadow: 0 8px 24px #0f172a0d; }}
.sticky {{ position: sticky; top: 20px; align-self: start; }}
audio {{ width: 100%; margin: 14px 0; }}
.progress {{ height: 10px; background: #e5e7eb; border-radius: 8px; overflow: hidden; }}
.progress span {{ display: block; width: 0; height: 100%; background: #16a34a; transition: width .2s; }}
.hash {{ font-family: ui-monospace, monospace; font-size: 12px; overflow-wrap: anywhere; color: #475569; }}
label.check {{ display: block; padding: 9px 0; line-height: 1.35; }}
input[type=checkbox] {{ width: 18px; height: 18px; vertical-align: -3px; margin-right: 8px; }}
input[type=text], textarea {{ box-sizing: border-box; width: 100%; padding: 10px; border: 1px solid #94a3b8; border-radius: 8px; }}
textarea {{ min-height: 90px; resize: vertical; }}
button {{ width: 100%; padding: 13px; border: 0; border-radius: 9px; font-weight: 700; background: #166534; color: white; }}
button:disabled {{ background: #94a3b8; cursor: not-allowed; }}
.status {{ padding: 10px 12px; border-radius: 8px; background: #eff6ff; margin: 12px 0; }}
.approved {{ background: #dcfce7; color: #166534; }}
.warning {{ background: #fff7ed; color: #9a3412; }}
details {{ margin-top: 12px; }}
pre {{ white-space: pre-wrap; font: 14px/1.55 ui-monospace, monospace; }}
.story {{ border-top: 1px solid #e2e8f0; padding-top: 12px; margin-top: 12px; }}
a {{ color: #1d4ed8; }}
@media (max-width: 800px) {{ .grid {{ grid-template-columns: 1fr; }} .sticky {{ position: static; }} }}
</style>
</head>
<body>
<main>
  <section class="hero">
    <div class="eyebrow">Unpublished local review</div>
    <h1 id="episode"></h1>
    <p>Listen to the exact file, inspect its evidence, and approve only when every gate is satisfied.</p>
  </section>
  <div class="grid">
    <section>
      <article class="card">
        <h2>Recording</h2>
        <audio id="audio" controls preload="metadata" src="/audio?token={token}"></audio>
        <div class="progress"><span id="coverageBar"></span></div>
        <p id="coverage">Listening coverage: 0%</p>
        <p class="hash" id="audioHash"></p>
      </article>
      <article class="card">
        <h2>Evidence and claims</h2>
        <div id="stories"></div>
      </article>
      <article class="card">
        <details><summary><strong>Exact transcript</strong></summary><pre id="transcript"></pre></details>
        <details><summary><strong>Show notes</strong></summary><pre id="notes"></pre></details>
      </article>
    </section>
    <aside class="card sticky">
      <h2>Approval checklist</h2>
      <div id="existing" class="status approved" hidden>This bundle already has an approval record.</div>
      <div id="playbackWarning" class="status warning">Complete at least 98% of the recording.</div>
      <form id="form">
        <label class="check"><input type="checkbox" name="disclosure">I heard the AI-production disclosure.</label>
        <label class="check"><input type="checkbox" name="first_useful_point">The first useful product point arrives within 30 seconds.</label>
        <label class="check"><input type="checkbox" name="claims">Every material spoken claim is supported by the displayed evidence.</label>
        <label class="check"><input type="checkbox" name="pronunciation">Names, numbers, and eligibility statements are pronounced clearly.</label>
        <label class="check"><input type="checkbox" name="pacing">Pacing, joins, loudness, and clipping have no unresolved defects.</label>
        <label class="check"><input type="checkbox" name="takeaways">Each main story has a useful change, workflow impact, and limitation.</label>
        <label class="check"><input type="checkbox" name="transcript">The transcript matches what I heard.</label>
        <p><label>Reviewer name<input id="reviewer" type="text" maxlength="100" autocomplete="name"></label></p>
        <p><label>Review notes<textarea id="reviewNotes" maxlength="4000" placeholder="Optional observations"></textarea></label></p>
        <button id="approve" type="submit" disabled>Approve this exact recording</button>
      </form>
      <p id="result" class="status" hidden></p>
      <p class="hash" id="manifestHash"></p>
      <p class="hash" id="transcriptHash"></p>
      <hr>
      <h2>Publication</h2>
      <p id="publishReason" class="status warning"></p>
      <button id="publish" type="button" disabled>Publish approved recording</button>
      <p id="publishResult" class="status" hidden></p>
      <p>Publication uploads immutable assets and queues the existing locked publisher. Subscriber confirmation occurs
      later in GitHub Actions.</p>
    </aside>
  </div>
</main>
<script>
const data = JSON.parse(new TextDecoder().decode(Uint8Array.from(atob("{encoded}"), c => c.charCodeAt(0))));
const token = {json.dumps(token)};
const audio = document.getElementById("audio");
const ranges = [];
let lastTime = null;
let playbackComplete = false;
const checks = [...document.querySelectorAll("input[type=checkbox]")];
const approve = document.getElementById("approve");
const publish = document.getElementById("publish");
document.getElementById("episode").textContent = data.episode_id;
document.getElementById("audioHash").textContent = "Audio SHA-256: " + data.audio_sha256;
document.getElementById("manifestHash").textContent = "Manifest SHA-256: " + data.manifest_sha256;
document.getElementById("transcriptHash").textContent = "Transcript SHA-256: " + data.transcript_sha256;
document.getElementById("transcript").textContent = data.transcript;
document.getElementById("notes").textContent = data.show_notes;
document.getElementById("existing").hidden = !data.already_approved;
document.getElementById("publishReason").textContent = data.publication_queued
  ? "Publication has already been queued for this exact bundle."
  : (data.publish_reason || "Available after listening approval.");

function addRange(start, end) {{
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start || end - start > 2) return;
  ranges.push([Math.max(0, start), Math.min(data.duration_secs, end)]);
  ranges.sort((a,b) => a[0] - b[0]);
  const merged = [];
  for (const range of ranges) {{
    const prior = merged[merged.length - 1];
    if (prior && range[0] <= prior[1] + .5) prior[1] = Math.max(prior[1], range[1]);
    else merged.push(range.slice());
  }}
  ranges.splice(0, ranges.length, ...merged);
}}
function listened() {{ return ranges.reduce((sum, range) => sum + range[1] - range[0], 0); }}
function update() {{
  const coverage = Math.min(100, 100 * listened() / data.duration_secs);
  document.getElementById("coverage").textContent = `Listening coverage: ${{coverage.toFixed(1)}}%`;
  document.getElementById("coverageBar").style.width = coverage + "%";
  playbackComplete = coverage >= 98;
  document.getElementById("playbackWarning").hidden = playbackComplete;
  approve.disabled = data.already_approved || !playbackComplete ||
    !checks.every(box => box.checked) || !document.getElementById("reviewer").value.trim();
  publish.disabled = !data.publish_allowed || !data.already_approved || data.publication_queued;
}}
audio.addEventListener("play", () => {{ lastTime = audio.currentTime; }});
audio.addEventListener("seeking", () => {{ lastTime = audio.currentTime; }});
audio.addEventListener("timeupdate", () => {{
  if (!audio.paused && lastTime !== null) addRange(lastTime, audio.currentTime);
  lastTime = audio.currentTime;
  update();
}});
audio.addEventListener("ended", () => {{
  addRange(0, Math.min(1, data.duration_secs));
  addRange(lastTime, data.duration_secs);
  update();
}});
checks.forEach(box => box.addEventListener("change", update));
document.getElementById("reviewer").addEventListener("input", update);

const stories = document.getElementById("stories");
for (const story of data.stories) {{
  const section = document.createElement("section");
  section.className = "story";
  const title = document.createElement("h3");
  title.textContent = story.headline;
  section.append(title);
  for (const [label, value] of [["What changed", story.what_changed], ["Why it matters", story.why_it_matters],
                                ["Recommendation", story.action.toUpperCase() + " — " + story.rationale]]) {{
    const p = document.createElement("p");
    const strong = document.createElement("strong");
    strong.textContent = label + ": ";
    p.append(strong, document.createTextNode(value));
    section.append(p);
  }}
  for (const claim of story.claims) {{
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = claim.text;
    const quote = document.createElement("blockquote");
    quote.textContent = claim.quote;
    const link = document.createElement("a");
    link.href = claim.url; link.target = "_blank"; link.rel = "noopener noreferrer";
    link.textContent = "Open primary source (" + claim.event_id + ")";
    details.append(summary, quote, link);
    section.append(details);
  }}
  stories.append(section);
}}
document.getElementById("form").addEventListener("submit", async event => {{
  event.preventDefault();
  approve.disabled = true;
  const response = await fetch("/approve?token=" + encodeURIComponent(token), {{
    method: "POST", headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify({{
      reviewer: document.getElementById("reviewer").value,
      notes: document.getElementById("reviewNotes").value,
      playback_complete: playbackComplete,
      listened_seconds: listened(),
      checks: Object.fromEntries(checks.map(box => [box.name, box.checked])),
    }}),
  }});
  const result = await response.json();
  const message = document.getElementById("result");
  message.hidden = false;
  message.className = "status " + (response.ok ? "approved" : "warning");
  message.textContent = response.ok ? "Approved. The hash-bound local record was saved; nothing was published." : result.error;
  if (response.ok) data.already_approved = true;
  update();
}});
publish.addEventListener("click", async () => {{
  if (!confirm("Upload these immutable bytes and queue the production publisher?")) return;
  publish.disabled = true;
  const response = await fetch("/publish?token=" + encodeURIComponent(token), {{
    method: "POST", headers: {{"Content-Type": "application/json"}}, body: "{{}}",
  }});
  const result = await response.json();
  const message = document.getElementById("publishResult");
  message.hidden = false;
  message.className = "status " + (response.ok ? "approved" : "warning");
  message.textContent = response.ok
    ? "Publication queued. GitHub Actions must still verify delivery and confirm the episode."
    : result.error;
  if (response.ok) {{
    data.publication_queued = true;
    document.getElementById("publishReason").textContent =
      "Publication has been queued for this exact bundle.";
  }}
  update();
}});
update();
</script>
</body>
</html>""".encode("utf-8")


def create_server(
    bundle: ReviewBundle, *, port: int = 8765, allow_publish: bool = False,
) -> ThreadingHTTPServer:
    token = secrets.token_urlsafe(24)
    class Handler(BaseHTTPRequestHandler):
        def _authorized(self) -> bool:
            return parse_qs(urlparse(self.path).query).get("token") == [token]

        def _send(self, status: int, content: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                "media-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'",
            )
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if not self._authorized():
                self._send(HTTPStatus.FORBIDDEN, b"Forbidden", "text/plain; charset=utf-8")
                return
            if parsed.path == "/":
                self._send(
                    HTTPStatus.OK,
                    _page(review_payload(bundle, allow_publish=allow_publish), token),
                    "text/html; charset=utf-8",
                )
                return
            if parsed.path != "/audio":
                self._send(HTTPStatus.NOT_FOUND, b"Not found", "text/plain; charset=utf-8")
                return
            size = bundle.audio_path.stat().st_size
            start, end = 0, size - 1
            header = self.headers.get("Range")
            if header:
                try:
                    unit, requested = header.split("=", 1)
                    first, last = requested.split("-", 1)
                    if unit != "bytes" or "," in requested:
                        raise ValueError
                    start = int(first) if first else max(0, size - int(last))
                    end = int(last) if last else size - 1
                    if not 0 <= start <= end < size:
                        raise ValueError
                except ValueError:
                    self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.end_headers()
                    return
                self.send_response(HTTPStatus.PARTIAL_CONTENT)
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            else:
                self.send_response(HTTPStatus.OK)
            with bundle.audio_path.open("rb") as stream:
                stream.seek(start)
                content = stream.read(end - start + 1)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path not in {"/approve", "/publish"} or not self._authorized():
                self._send(HTTPStatus.FORBIDDEN, b'{"error":"Forbidden"}', "application/json")
                return
            try:
                if self.headers.get_content_type() != "application/json":
                    raise ValueError("approval requires application/json")
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 65536:
                    raise ValueError("invalid request size")
                submission = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(submission, dict):
                    raise ValueError("request must be a JSON object")
                if path == "/approve":
                    approval = record_approval(bundle, submission)
                    result = {"approved": True, "approved_at": approval["approved_at"]}
                else:
                    queued = queue_publication(bundle, allow_publish=allow_publish)
                    result = {
                        "queued": True, "queued_at": queued["queued_at"],
                        "workflow": queued["workflow"],
                    }
                response = json.dumps(result).encode()
                self._send(HTTPStatus.CREATED, response, "application/json")
            except (
                FileExistsError,
                OSError,
                RuntimeError,
                subprocess.SubprocessError,
                UnicodeDecodeError,
                json.JSONDecodeError,
                ValueError,
            ) as exc:
                response = json.dumps({"error": str(exc)}).encode()
                self._send(HTTPStatus.BAD_REQUEST, response, "application/json")

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.review_url = f"http://127.0.0.1:{server.server_port}/?token={token}"  # type: ignore[attr-defined]
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True, help="Unpublished preview or prepared bundle")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true", help="Print the local URL without opening a browser")
    parser.add_argument(
        "--allow-publish", action="store_true",
        help="Expose publication for approved schema-3/4 bundles; previews remain blocked",
    )
    args = parser.parse_args(argv)
    bundle = load_review_bundle(args.directory)
    server = create_server(bundle, port=args.port, allow_publish=args.allow_publish)
    url = server.review_url  # type: ignore[attr-defined]
    print(f"Reviewing {bundle.manifest.episode_id}")
    print(url)
    print(f"Approval record: {bundle.approval_path}")
    print("Press Ctrl+C to stop.")
    if args.allow_publish:
        print("Publication remains blocked for previews and requires approval plus GitHub/main preflight checks.")
    else:
        print("Publication is disabled. Restart with --allow-publish for an eligible reviewed bundle.")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
