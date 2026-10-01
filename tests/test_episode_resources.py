import json
from pathlib import Path
import xml.etree.ElementTree as ET
import pytest
from PIL import Image
from pipeline.audio import file_sha256
from pipeline.episode_resources import stage_resources, NAMESPACE
from pipeline.podcast import render_feed
from tests.test_reviewed_audio import draft


def setup(tmp_path):
    bundle = tmp_path / "bundle"; bundle.mkdir()
    audio = bundle / "daily-ai-brief.mp3"; audio.write_bytes(b"mock audio" * 2000)
    data = draft(audio.read_bytes()); data["status"] = "ready"
    data["audio"].update(size_bytes=audio.stat().st_size, sha256=file_sha256(audio),duration_secs=360,codec="mp3",sample_rate=44100,channels=2)
    (bundle / "episode-manifest.json").write_text(json.dumps(data))
    timings=tmp_path / "timings.json"
    timings.write_text(json.dumps({"audio_sha256":file_sha256(audio),"segments":[{"start":0,"end":120,"text":"A clear first point."},{"start":120,"end":360.2,"text":"A useful second point."}],"chapters":[{"startTime":0,"title":"First point"},{"startTime":120,"title":"Second point"}]}))
    feed=tmp_path / "feed.xml"
    feed.write_text(render_feed([{"guid":data["episode_id"],"mp3_url":data["audio"]["url"],"file_size_bytes":audio.stat().st_size,"title":"Test","description":"Reviewed test","pub_date":data["published_at"],"duration_secs":360}]))
    tree=ET.parse(feed); ET.SubElement(tree.getroot().find("channel"),"historical-extension").text="preserve"; tree.write(feed)
    art=tmp_path / "art.jpg"; Image.new("RGB",(1400,1400)).save(art)
    return bundle,timings,feed,art


def test_stages_bound_resources_and_preserves_history(tmp_path):
    bundle,timings,feed,art=setup(tmp_path)
    original=feed.read_bytes()
    receipt=stage_resources(bundle,timings,feed,art,tmp_path / "out")
    assert receipt["remote_verified"] is False
    assert receipt["asr_ends_clipped_to_measured_duration"] == 1
    root=ET.parse(tmp_path / "out/podcast.xml").getroot()
    assert root.findtext("channel/historical-extension") == "preserve"
    assert root.find(f"channel/item/{{{NAMESPACE}}}chapters").get("type") == "application/json+chapters"
    assert root.find(f"channel/item/{{{NAMESPACE}}}transcript").get("type") == "text/vtt"
    assert "00:06:00.000" in next((tmp_path / "out").rglob("*.vtt")).read_text()
    assert feed.read_bytes() == original


@pytest.mark.parametrize("change", [
    lambda p: p.update(audio_sha256="0"*64),
    lambda p: p["chapters"][1].update(startTime=123),
    lambda p: p["segments"][1].update(end=400),
    lambda p: p["segments"][1].update(start=100),
])
def test_unbound_or_estimated_timings_fail_before_writing(change,tmp_path):
    bundle,timings,feed,art=setup(tmp_path)
    data=json.loads(timings.read_text());change(data);timings.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        stage_resources(bundle,timings,feed,art,tmp_path / "out")
    assert not (tmp_path / "out").exists()
