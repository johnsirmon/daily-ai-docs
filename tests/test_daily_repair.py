"""Offline regression checks for cadence, research fallback, and service outages."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from pipeline.daily import prepare
from pipeline.models_client import EditorialConfigurationError, EditorialProviderError, editorial_model_config
from pipeline.podcast import load_episodes, prepend_episode, write_feed
from pipeline.publish import PublicationError, validate_feed_file
from pipeline.rank import select_editorial_events
from pipeline.run_health import skip_candidate
from pipeline.schema import SchemaError
from pipeline.synthesis import refine_editorial
from pipeline.video_bundle import build_bundle
from tests.test_grounded_editorial import (approval, base_story, draft, event, manifest,
                                          research_case, response)
from tests.test_podcast import _ep


def test_quiet_research_requires_opt_in_and_fresh_uncovered_full_text():
    paper, _, _ = research_case()
    now = datetime(2026, 9, 17, tzinfo=timezone.utc)
    assert not select_editorial_events([paper], now=now)[0]
    assert select_editorial_events([paper], now=now, quiet_news_research=True)[0] == [paper]
    assert not select_editorial_events([paper], now=now, quiet_news_research=True,
                                       covered_paper_ids=[paper.metadata['paper_id']])[0]
    assert not select_editorial_events([paper], now=now + timedelta(days=31), quiet_news_research=True)[0]
    paper.metadata['full_text_available'] = False
    assert not select_editorial_events([paper], now=now, quiet_news_research=True)[0]


@pytest.mark.parametrize('stage', ['draft', 'verify'])
def test_503_retry_preserves_independent_verification_and_actual_calls(stage):
    class Unavailable(RuntimeError):
        status_code = 503
    proposal = draft()
    client = MagicMock()
    outputs = [response(proposal), response(approval(proposal))]
    outputs.insert(0 if stage == 'draft' else 1, Unavailable('private provider details'))
    client.chat.completions.create.side_effect = outputs
    with patch('pipeline.synthesis.get_editorial_client', return_value=client), patch('pipeline.synthesis.time.sleep') as delay:
        stories, generation = refine_editorial([event()], [base_story([event()])], [], config={'service_retries': 2})
    assert generation['calls'] == generation['request_attempts'] == 3
    assert generation['editorial_version'] == 2
    assert client.chat.completions.create.call_count == 3
    delay.assert_called_once_with(10)
    result = manifest(stories, generation)
    result.validate(require_audio=False)
    generation['request_attempts'] = 2
    with pytest.raises(SchemaError, match='actual request attempts'):
        manifest(stories, generation)


def test_exhausted_503_stops_without_fallback():
    class Unavailable(RuntimeError):
        status_code = 503
    client = MagicMock()
    client.chat.completions.create.side_effect = Unavailable('sensitive')
    with patch('pipeline.synthesis.get_editorial_client', return_value=client), patch('pipeline.synthesis.time.sleep') as delay:
        with pytest.raises(EditorialProviderError, match='HTTP 503'):
            refine_editorial([event()], [base_story([event()])], [], config={'service_retries': 2})
    assert client.chat.completions.create.call_count == 3
    assert [call.args[0] for call in delay.call_args_list] == [10, 20]


@pytest.mark.parametrize('status', [400, 401, 403, 429, 500])
def test_retry_policy_does_not_retry_other_failures(status):
    failure = RuntimeError('sensitive')
    failure.status_code = status
    client = MagicMock()
    client.chat.completions.create.side_effect = failure
    with patch('pipeline.synthesis.get_editorial_client', return_value=client), patch('pipeline.synthesis.time.sleep') as delay:
        with pytest.raises(EditorialProviderError):
            refine_editorial([event()], [base_story([event()])], [], config={'service_retries': 2})
    assert client.chat.completions.create.call_count == 1
    delay.assert_not_called()


@pytest.mark.parametrize('retries', [-1, 3, True, '2'])
def test_retry_attempt_budget_is_bounded(retries):
    with pytest.raises(EditorialConfigurationError, match='service_retries'):
        editorial_model_config({'service_retries': retries})


def test_research_review_verified_and_video_plan_retains_sources():
    paper, _, proposal = research_case()
    client = MagicMock()
    client.chat.completions.create.side_effect = [response(proposal), response(approval(proposal))]
    with patch('pipeline.synthesis.get_editorial_client', return_value=client):
        stories, generation = refine_editorial([paper], [base_story([paper])], [])
    result = manifest(stories, generation, [paper])
    bundle = build_bundle(result)
    assert bundle['chapters'][0]['research_review']['limitations'] in bundle['transcript']
    assert bundle['chapters'][0]['source_urls'] == [paper.url]
    assert bundle['status'] == 'unpublished_video_plan'
    assert bundle['captions']['timing_status'] == 'requires_alignment_to_final_audio'
    for call in client.chat.completions.create.call_args_list:
        assert 'quiet-news research review edition' in call.kwargs['messages'][0]['content']


def test_duplicate_daily_date_uses_utc_boundary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('AI_EDITORIAL', 'off')
    config = tmp_path / 'topics.yaml'
    config.write_text('daily: {}')
    (tmp_path / 'data').mkdir()
    (tmp_path / 'data/state.json').write_text(json.dumps({
        'schema_version': 1, 'seen_event_ids': [], 'last_publication': '2026-10-05T23:30:00-04:00',
    }))
    with patch('pipeline.daily.collect_events') as collect:
        with pytest.raises(RuntimeError, match='already published'):
            prepare(config, now=datetime(2026, 10, 6, 10, tzinfo=timezone.utc))
    collect.assert_not_called()


def test_prepare_research_only_passes_full_contract_without_audio(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('AI_EDITORIAL', 'required')
    paper, row, proposal = research_case()
    row['story_id'] = 'story:e1'
    extra = ('The authors retained command traces and task outcomes to distinguish failures '
             'during execution from failures during evaluation, while the sandbox prevented '
             'external services from affecting the recorded task results. '
             'The fixture study describes isolated filesystem operations, preserved repository snapshots, '
             'and reviewed terminal output as supporting evidence for the evaluation process, '
             'without making claims about tool performance outside the recorded environment.')
    paper.metadata['full_text'] += ' ' + extra
    row['editorial']['spoken_text'] += (
        ' Preserved command traces let the researchers separate execution problems from '
        'evaluation problems. The isolated sandbox excludes effects from external services. '
        'Filesystem operations, repository snapshots and terminal output support inspection '
        'of the recorded process. Those records do not establish how tools perform outside '
        'that environment. Developers should interpret the outcomes within the documented '
        'sandbox conditions rather than assume equivalent production behavior.'
    )
    row['editorial']['claims'].append({'text': extra, 'event_id': paper.event_id, 'quote': extra})
    config = tmp_path / 'topics.yaml'
    config.write_text('daily:\n  editorial:\n    enabled: true\n    quiet_news_research: true\n    minimum_words: 100\n    maximum_words: 300\n')
    client = MagicMock()
    client.chat.completions.create.side_effect = [response(proposal), response(approval(proposal))]
    with patch('pipeline.daily.collect_events', return_value=([paper], {'github:tool': 'ok:0'})), \
         patch('pipeline.synthesis.get_editorial_client', return_value=client), \
         patch('pipeline.daily.write_audio') as audio:
        result = prepare(config, no_audio=True, now=datetime(2026, 9, 17, 12, tzinfo=timezone.utc))
    assert result['outcome'] == 'publish'
    saved = json.loads((tmp_path / result['manifest_path']).read_text())
    assert saved['generation']['edition'] == 'research-review'
    assert saved['source_events'][0]['metadata']['full_text_retained'] is False
    assert 'full_text' not in saved['source_events'][0]['metadata']
    audio.assert_not_called()
    assert not (tmp_path / 'podcast.xml').exists()
    assert not (tmp_path / 'data/state.json').exists()


def test_new_daily_id_is_today_not_source_date(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / 'topics.yaml'
    config.write_text('daily:\n  minimum_score: 0\n')
    with patch('pipeline.daily.collect_events', return_value=([event()], {'github:tool': 'ok:1'})):
        result = prepare(config, dry_run=True, no_audio=True, now=datetime(2026, 10, 6, 0, 1, tzinfo=timezone.utc))
    assert result['episode_id'].startswith('daily-2026-10-06-')


def test_retains_more_than_sixty_items_and_duplicate_guid(tmp_path, monkeypatch):
    monkeypatch.delenv('PODCAST_MAX_EPISODES', raising=False)
    path = str(tmp_path / 'feed.xml')
    episodes = [{**_ep(1), 'guid': f'episode-{i}', 'mp3_url': f'https://example.com/{i}.mp3'} for i in range(65)]
    write_feed(episodes, path=path)
    prepend_episode(_ep(2), path=path)
    assert len(load_episodes(path)) == 66
    original = (tmp_path / 'feed.xml').read_bytes()
    prepend_episode(_ep(2), path=path)
    assert (tmp_path / 'feed.xml').read_bytes() == original


@pytest.mark.parametrize('old,new', [('https://', 'http://'), ('audio/mpeg', 'text/html')])
def test_enclosures_require_https_and_mp3(tmp_path, old, new):
    path = tmp_path / 'feed.xml'
    write_feed([_ep()], path=str(path))
    path.write_text(path.read_text().replace(old, new))
    with pytest.raises(PublicationError, match='HTTPS MP3'):
        validate_feed_file(path)


@pytest.mark.parametrize('status', ['skipped', 'published'])
def test_fresh_special_or_skip_cannot_hide_old_daily_delivery(tmp_path, monkeypatch, status):
    monkeypatch.chdir(tmp_path)
    now = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)
    (tmp_path / 'data/runs').mkdir(parents=True)
    path = tmp_path / 'data/runs/latest.json'
    path.write_text(json.dumps({'schema_version': 1, 'status': status, 'evaluated_at': now.isoformat()}))
    (tmp_path / 'data/state.json').write_text(json.dumps({
        'schema_version': 2, 'last_publication': now.isoformat(),
        'last_daily_publication': (now - timedelta(hours=26)).isoformat(),
    }))
    with pytest.raises(PublicationError, match='daily delivery is stale'):
        skip_candidate(path, now=now, require_daily_delivery=True)
