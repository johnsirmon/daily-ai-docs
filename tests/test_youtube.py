import json
from datetime import datetime, timezone

from pipeline.narrate import manifest_to_narration
from pipeline.rank import event_to_story
from pipeline.schema import EpisodeManifest
from pipeline.sources.youtube import collect_youtube_digest
from pipeline.youtube import discover_videos


class Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class Session:
    def get(self, url, params, timeout):
        if url.endswith("/search"):
            return Response({"items": [
                {"id": {"videoId": "video-a"}},
                {"id": {"videoId": "video-b"}},
            ]})
        return Response({"items": [
            {
                "id": "video-a",
                "snippet": {
                    "title": "Build reliable coding agents",
                    "channelId": "channel-a",
                    "channelTitle": "Agent Engineering",
                    "publishedAt": "2026-09-06T12:00:00Z",
                    "description": "Implementation notes: https://openai.com/research/example",
                },
                "statistics": {"viewCount": "12000", "likeCount": "900"},
            },
            {
                "id": "video-b",
                "snippet": {
                    "title": "AI roundup",
                    "channelId": "channel-b",
                    "channelTitle": "General AI",
                    "publishedAt": "2026-09-01T12:00:00Z",
                    "description": "No primary links.",
                },
                "statistics": {"viewCount": "1000", "likeCount": "10"},
            },
        ]})


def transcript(video_id):
    if video_id == "video-a":
        return (
            "The implementation uses evaluation traces to test an agent workflow before deployment. "
            "A practical debugging loop records tool calls and checks whether context was actually useful. "
            "The benchmark compares the same coding task with and without durable memory."
        )
    return "A short generic introduction without enough implementation detail to be useful."


def test_discovery_ranks_age_adjusted_transcript_backed_videos():
    payload = discover_videos(
        {
            "queries": ["coding agents", "agent evaluation"],
            "max_selected": 1,
            "primary_domains": ["openai.com"],
        },
        api_key="test-key",
        now=datetime(2026, 9, 7, 12, tzinfo=timezone.utc),
        session=Session(),
        transcript_fetcher=transcript,
    )
    assert payload["query_count"] == 2
    assert payload["candidate_count"] == 2
    assert [video["video_id"] for video in payload["videos"]] == ["video-a"]
    video = payload["videos"][0]
    assert video["views_per_day"] > 0
    assert video["trend_score"] > 0
    assert "evaluation traces" in video["takeaway"]
    assert video["primary_urls"] == ["https://openai.com/research/example"]
    assert "description" not in video
    assert "transcript" not in video


def test_discovery_excludes_video_without_transcript():
    payload = discover_videos(
        {"queries": ["coding agents"], "require_transcript": True},
        api_key="test-key",
        now=datetime(2026, 9, 7, 12, tzinfo=timezone.utc),
        session=Session(),
        transcript_fetcher=lambda _: "",
    )
    assert payload["videos"] == []


def test_digest_adapter_emits_bounded_source_event(tmp_path):
    path = tmp_path / "youtube.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "generated_at": "2026-09-07T12:00:00Z",
        "videos": [{
            "video_id": "video-a",
            "title": "Build reliable coding agents",
            "channel_title": "Agent Engineering",
            "published_at": "2026-09-06T12:00:00Z",
            "takeaway": "Trace tool calls and evaluate the same task before and after a workflow change.",
            "trend_score": 88.0,
            "views_per_day": 12000.0,
            "channel_velocity_ratio": 1.8,
            "primary_urls": ["https://openai.com/research/example"],
        }],
    }), encoding="utf-8")
    events, health = collect_youtube_digest(
        {"digest_path": str(path)},
        now=datetime(2026, 9, 8, 12, tzinfo=timezone.utc),
    )
    assert health == {"youtube:weekly-digest": "ok:1"}
    assert len(events) == 1
    assert events[0].source_type == "youtube_video"
    assert events[0].metadata["corroboration_urls"] == ["https://openai.com/research/example"]


def test_digest_adapter_rejects_stale_digest(tmp_path):
    path = tmp_path / "youtube.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "generated_at": "2026-08-01T12:00:00Z",
        "videos": [],
    }), encoding="utf-8")
    events, health = collect_youtube_digest(
        {"digest_path": str(path), "max_digest_age_days": 9},
        now=datetime(2026, 9, 8, 12, tzinfo=timezone.utc),
    )
    assert events == []
    assert health == {"youtube:weekly-digest": "error:ValueError"}


def test_video_story_is_framed_as_a_learning_pick(tmp_path):
    path = tmp_path / "youtube.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "generated_at": "2026-09-07T12:00:00Z",
        "videos": [{
            "video_id": "video-a",
            "title": "Build reliable coding agents",
            "channel_title": "Agent Engineering",
            "published_at": "2026-09-06T12:00:00Z",
            "takeaway": "Trace tool calls before changing an agent workflow.",
            "trend_score": 88,
            "primary_urls": [],
        }],
    }), encoding="utf-8")
    events, _ = collect_youtube_digest(
        {"digest_path": str(path)},
        now=datetime(2026, 9, 8, 12, tzinfo=timezone.utc),
    )
    story = event_to_story(events[0])
    manifest = EpisodeManifest(
        1, "daily-test", "2026-09-08T12:00:00Z", "draft", {"youtube": "ok:1"},
        events, [story], [], "pending", "notes", {"edition": "alert"}, {},
    )
    narration = manifest_to_narration(manifest)
    assert "For your focused learning queue" in narration
    assert story.action == "watch"
    assert "not verified product-change evidence" in narration
    assert "does not establish adoption" in narration
