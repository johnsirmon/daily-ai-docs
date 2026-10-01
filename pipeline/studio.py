"""Portable private production, using the existing reviewed-audio contract.

No workflow dispatch, publishing, credential installation or implicit paid provider.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import html
import json
import os
from pathlib import Path
import shutil
import time

from .audio import analyze_audio, file_sha256
from .disclosure import episode_metadata_disclosure
from .publish import validate_episode_artwork, validate_feed_file
from .reviewed_audio import prepare_reviewed_audio
from .schema import EpisodeManifest
from .tts import write_audio


def _write(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


@contextmanager
def _owner(directory: Path):
    if directory.is_symlink():
        raise ValueError("output cannot be a symlink")
    if directory.exists() and any(directory.iterdir()) and not any((directory / name).exists() for name in ("synthesis.json", "studio-receipt.json")):
        raise ValueError("output already contains unrelated artifacts")
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / ".studio.lock"
    with lock.open("x") as stream:
        stream.write(str(os.getpid()))
    try:
        yield
    finally:
        lock.unlink()


@contextmanager
def _environment(**values):
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def synthesize(script: Path, output: Path, *, confirmed: bool = False,
               voice: str = "en-US-AndrewMultilingualNeural", rate: str = "-5%") -> dict:
    """Free Edge only; bounded retry, frozen script/settings and reusable receipt."""
    if not confirmed:
        raise ValueError("networked Edge synthesis requires --free-edge-confirmed")
    text = script.read_text(encoding="utf-8")
    if not 100 <= len(text.split()) <= 1500:
        raise ValueError("a daily script must contain 100-1500 words before synthesis")
    identity = {"script_sha256": file_sha256(script), "provider": "edge", "voice": voice, "rate": rate, "pitch": "+0Hz"}
    with _owner(output):
        receipt = output / "synthesis.json"
        audio = output / "source.mp3"
        previous = json.loads(receipt.read_text()) if receipt.exists() else {}
        if previous and previous.get("input") != identity:
            raise ValueError("changed script or voice requires a new output directory")
        if audio.exists():
            if previous.get("audio_sha256") != file_sha256(audio):
                raise ValueError("audio has no matching receipt; preserve it and use a new output")
            return previous
        state = {"input": identity, "status": "synthesizing", "attempts": previous.get("attempts", 0)}
        while state["attempts"] < 3:
            state["attempts"] += 1
            _write(receipt, state)
            with _environment(TTS_PROVIDER="edge", EDGE_TTS_VOICE=voice, EDGE_TTS_RATE=rate,
                              EDGE_TTS_PITCH="+0Hz", EDGE_TTS_VOLUME="+0%"):
                produced = write_audio(text, str(output / "attempt.mp3"))
            if produced is not None:
                analyze_audio(produced, min_duration_secs=20, max_duration_secs=480,
                              expected_word_count=len(text.split()))
                os.replace(produced, audio)
                state.update(status="recorded_needs_review", audio_sha256=file_sha256(audio))
                _write(receipt, state)
                return state
            state.update(status="provider_unavailable", reason="Edge returned no usable audio; no provider fallback")
            _write(receipt, state)
            if state["attempts"] < 3:
                time.sleep(2 ** (state["attempts"] - 1))
        raise RuntimeError("Edge unavailable after three attempts; receipt retained, no paid fallback")


def _page(manifest: EpisodeManifest, title: str) -> str:
    esc = html.escape
    cards = "".join(
        f'<article><p class="eyebrow">{esc(story.action.upper())}</p><h2>{esc(story.headline)}</h2>'
        f'<p>{esc(story.why_it_matters)}</p><p><strong>Try this:</strong> {esc(story.rationale)}</p>'
        + '<details><summary>Primary evidence</summary><ul>'
        + "".join(f'<li><a href="{esc(url, quote=True)}">{esc(url)}</a></li>' for url in story.source_urls)
        + '</ul></details></article>' for story in manifest.stories
    )
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} — Daily AI Developer Brief</title><link rel="stylesheet" href="studio.css">
<a class="skip" href="#content">Skip to the brief</a>
<header><div><p class="eyebrow">DAILY AI DEVELOPER BRIEF · {esc(manifest.published_at[:10])}</p>
<p class="status">Private listening candidate · not published</p><h1>{esc(title)}</h1>
<p class="dek">Fewer release numbers. More decisions you can verify.</p>
<audio controls preload="metadata" src="bundle/daily-ai-brief.mp3">Download the MP3 below.</audio>
<p><a href="bundle/daily-ai-brief.mp3">Download audio</a> · <a href="#transcript">Read transcript</a></p>
<p class="small">{manifest.audio['duration_secs']/60:.1f} minutes · No sponsors or ads</p></div>
<img src="episode.jpg" width="1600" height="1600" alt="Conceptual illustration of a clear signal connecting layered cards"></header>
<main id="content"><section class="decisions" aria-label="Practical decisions">{cards}</section>
<section class="flow"><p class="eyebrow">SUGGESTED INTEGRATION CHECK</p><h2>Follow the boundary, not the version number.</h2>
<ol><li><b>Discover</b><span>Are the expected tools visible?</span></li><li><b>Scope</b><span>Which origin and directory are approved?</span></li><li><b>Execute</b><span>Use a harmless test task.</span></li><li><b>Inspect</b><span>Record the result before changing defaults.</span></li></ol>
<p class="small">An editorial test sequence, not a diagram of product internals or measured results.</p></section>
<section id="transcript"><h2>Full transcript</h2><p class="transcript">{esc(manifest.narration)}</p></section>
<section><h2>Source notes</h2><p class="transcript">{esc(manifest.show_notes)}</p></section></main>
<footer><p>{esc(episode_metadata_disclosure(manifest.schema_version))}</p><p>Local ASR and technical checks do not replace listening review. This candidate has not been delivered to subscribers.</p></footer></html>"""


def build(draft: Path, audio: Path, feed: Path, artwork: Path, output: Path, *, title: str) -> dict:
    """One offline command: import/master, validate, build candidate feed and listening page.

    The operator supplies an actual transcript/source-reviewed draft. Publication
    remains a separate explicit action; the canonical feed is never modified.
    """
    for path in (draft, audio, feed, artwork):
        if path.is_symlink() or not path.is_file():
            raise ValueError("inputs must be existing regular files")
        if output.resolve() == path.resolve() or output.resolve() in path.resolve().parents:
            raise ValueError("output cannot contain an input")
    identity = {name: file_sha256(path) for name, path in
                (("draft", draft), ("audio", audio), ("feed", feed), ("artwork", artwork))}
    identity["title"] = title
    identity["renderer"] = file_sha256(Path(__file__))
    identity["stylesheet"] = file_sha256(Path(__file__).resolve().parents[1] / "assets/studio/studio.css")
    validate_episode_artwork(artwork.read_bytes())
    with _owner(output):
        receipt = output / "studio-receipt.json"
        previous = json.loads(receipt.read_text()) if receipt.exists() else {}
        if previous and previous.get("input") != identity:
            raise ValueError("changed input requires a new candidate directory")
        if previous.get("status") == "ready_for_listening":
            for name, digest in previous["outputs"].items():
                if file_sha256(output / name) != digest:
                    raise ValueError("candidate artifact changed; refusing unsafe resume")
            return previous
        state = {"input": identity, "status": "building", "published": False}
        _write(receipt, state)
        try:
            bundle = output / "bundle"
            if not bundle.exists():
                with _environment(PODCAST_AUDIO_POLISH="1"):
                    prepare_reviewed_audio(draft, audio, bundle)
            manifest = EpisodeManifest.from_dict(json.loads((bundle / "episode-manifest.json").read_text()))
            from .reviewed_duration import reviewed_duration_bounds
            minimum, maximum = reviewed_duration_bounds(manifest)
            measured = analyze_audio(bundle / "daily-ai-brief.mp3", min_duration_secs=minimum, max_duration_secs=maximum,
                                     expected_word_count=len(manifest.narration.split()))
            if measured["sha256"] != manifest.audio["sha256"]:
                raise ValueError("prepared bundle audio changed")
            expected = EpisodeManifest.from_dict(json.loads(draft.read_text())).to_dict()
            actual = manifest.to_dict()
            for row in (expected, actual):
                row.pop("status")
                row.pop("audio")
                row["generation"].pop("quality", None)
            if actual != expected:
                raise ValueError("prepared bundle does not match the reviewed draft")
            if manifest.generation["source_audio_sha256"] != identity["audio"]:
                raise ValueError("prepared bundle belongs to different source audio")
            shutil.copyfile(artwork, output / "episode.jpg")
            candidate = output / "feed-preview.xml"
            shutil.copyfile(feed, candidate)
            from .podcast import render_feed
            import xml.etree.ElementTree as ET
            new_episode = {"guid": manifest.episode_id, "title": title,
                             "description": manifest.show_notes + "\n\n" + episode_metadata_disclosure(manifest.schema_version),
                             "pub_date": manifest.published_at, "mp3_url": manifest.audio["url"],
                             "file_size_bytes": manifest.audio["size_bytes"],
                             "duration_secs": manifest.audio["duration_secs"]}
            # Insert one new item into the existing tree: retain every historical
            # GUID, enclosure and extension element instead of reconstructing it.
            tree = ET.parse(candidate)
            channel = tree.getroot().find("channel")
            if channel is None:
                raise ValueError("source feed has no channel")
            if any(item.findtext("guid") == manifest.episode_id for item in channel.findall("item")):
                raise ValueError("candidate identity is already in the source feed")
            item = ET.fromstring(render_feed([new_episode])).find("channel/item")
            channel.insert(0, item)
            tree.write(candidate, encoding="utf-8", xml_declaration=True)
            validate_feed_file(candidate)
            (output / "index.html").write_text(_page(manifest, title), encoding="utf-8")
            shutil.copyfile(Path(__file__).resolve().parents[1] / "assets/studio/studio.css", output / "studio.css")
            files = ["bundle/episode-manifest.json", "bundle/daily-ai-brief.mp3", "feed-preview.xml", "episode.jpg", "index.html", "studio.css"]
            state.update(status="ready_for_listening", episode_id=manifest.episode_id,
                         outputs={name: file_sha256(output / name) for name in files})
            _write(receipt, state)
            return state
        except Exception as exc:
            state.update(status="failed", error_type=type(exc).__name__,
                         reason="Candidate build failed; inputs and partial artifacts preserved. Inspect the failing stage before resuming.")
            _write(receipt, state)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    render = commands.add_parser("synthesize")
    render.add_argument("--script", type=Path, required=True)
    render.add_argument("--output", type=Path, required=True)
    render.add_argument("--voice", default="en-US-AndrewMultilingualNeural")
    render.add_argument("--rate", default="-5%")
    render.add_argument("--free-edge-confirmed", action="store_true")
    prepare = commands.add_parser("build")
    for name in ("draft", "audio", "feed", "artwork", "output"):
        prepare.add_argument("--" + name, type=Path, required=True)
    prepare.add_argument("--title", required=True)
    args = vars(parser.parse_args())
    command = args.pop("command")
    if command == "synthesize":
        args["confirmed"] = args.pop("free_edge_confirmed")
        result = synthesize(**args)
    else:
        result = build(**args)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
