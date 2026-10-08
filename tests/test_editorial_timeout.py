"""Offline SDK timeout regressions; no provider requests or publishing."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

try:
    import httpx2 as httpx
except ImportError:  # SDK 1.x/2.x use the original HTTPX package.
    import httpx
from openai import APIConnectionError, APITimeoutError
import pytest
import yaml

from pipeline.daily import prepare
from pipeline.models_client import EditorialProviderError, GEMINI_BASE_URL, editorial_model_config
from pipeline.synthesis import _request_editorial, refine_editorial
from tests.test_grounded_editorial import approval, base_story, draft, event, manifest, response


def timeout_error():
    return APITimeoutError(request=httpx.Request('POST', GEMINI_BASE_URL+'chat/completions'))


@pytest.mark.parametrize('stage', ['draft', 'verify'])
def test_typed_timeout_recovers_without_skipping_independent_verification(stage):
    proposal=draft()
    outputs=[response(proposal),response(approval(proposal))]
    outputs.insert(0 if stage=='draft' else 1,timeout_error())
    client=MagicMock()
    client.chat.completions.create.side_effect=outputs
    with patch('pipeline.synthesis.get_editorial_client',return_value=client) as provider, \
         patch('pipeline.synthesis.time.sleep') as delay:
        stories,generation=refine_editorial([event()],[base_story([event()])],[],config={'service_retries':2})
    assert generation['calls']==generation['request_attempts']==3
    assert generation['verified'] is True
    manifest(stories,generation).validate(require_audio=False)
    provider.assert_called_once()
    delay.assert_called_once_with(10)
    calls=client.chat.completions.create.call_args_list
    assert all(c.kwargs['model']=='gemini-3.8-flash' for c in calls)
    retry_index = 0 if stage == 'draft' else 1
    assert calls[retry_index].kwargs == calls[retry_index + 1].kwargs
    assert calls[-1].kwargs['max_tokens']==2500
    assert calls[0].kwargs['max_tokens']==4000
    assert all(c.kwargs['reasoning_effort']=='low' for c in calls)


def test_503_then_timeout_share_one_attempt_ceiling():
    unavailable=RuntimeError('sensitive provider detail')
    unavailable.status_code=503
    client=MagicMock()
    proposal=draft()
    client.chat.completions.create.side_effect=[unavailable,timeout_error(),response(proposal),response(approval(proposal))]
    with patch('pipeline.synthesis.get_editorial_client',return_value=client),patch('pipeline.synthesis.time.sleep') as delay:
        stories,generation=refine_editorial([event()],[base_story([event()])],[],config={'service_retries':2})
    assert generation['calls']==4
    assert [c.args[0] for c in delay.call_args_list]==[10,20]
    manifest(stories,generation).validate(require_audio=False)


@pytest.mark.parametrize('retries,expected',[(0,1),(1,2),(2,3)])
def test_timeout_exhaustion_and_opt_in_limits(retries,expected):
    client=MagicMock()
    client.chat.completions.create.side_effect=timeout_error()
    with patch('pipeline.synthesis.get_editorial_client',return_value=client),patch('pipeline.synthesis.time.sleep'):
        with pytest.raises(EditorialProviderError,match=r'\(timeout\).*no publication fallback'):
            refine_editorial([event()],[base_story([event()])],[],config={'service_retries':retries})
    assert client.chat.completions.create.call_count==expected


def test_unclassified_connection_failure_does_not_retry():
    client=MagicMock()
    client.chat.completions.create.side_effect=APIConnectionError(request=httpx.Request('POST',GEMINI_BASE_URL))
    with patch('pipeline.synthesis.get_editorial_client',return_value=client),patch('pipeline.synthesis.time.sleep') as delay:
        with pytest.raises(EditorialProviderError):
            refine_editorial([event()],[base_story([event()])],[],config={'service_retries':2})
    assert client.chat.completions.create.call_count==1
    delay.assert_not_called()


def test_deadline_caps_timeout_and_rejects_unaffordable_backoff():
    client=MagicMock()
    client.chat.completions.create.side_effect=timeout_error()
    with patch('pipeline.synthesis.time.monotonic',side_effect=[10,15]),patch('pipeline.synthesis.time.sleep') as delay:
        with pytest.raises(EditorialProviderError,match='time budget exhausted'):
            _request_editorial(client,model='gemini-3.8-flash',instructions='Evidence only',payload={},
                max_input_chars=2000,max_output_tokens=4000,timeout=60,service_retries=2,deadline=20)
    assert client.chat.completions.create.call_args.kwargs['timeout']==10
    assert client.chat.completions.create.call_count==1
    delay.assert_not_called()


def test_six_attempts_remain_the_maximum_for_two_successful_stages():
    proposal=draft()
    client=MagicMock()
    client.chat.completions.create.side_effect=[timeout_error(),timeout_error(),response(proposal),
        timeout_error(),timeout_error(),response(approval(proposal))]
    with patch('pipeline.synthesis.get_editorial_client',return_value=client),patch('pipeline.synthesis.time.sleep'):
        stories,generation=refine_editorial([event()],[base_story([event()])],[],config={'service_retries':2})
    assert generation['calls']==generation['request_attempts']==6
    manifest(stories,generation).validate(require_audio=False)


def test_exhausted_timeouts_cannot_write_audio_feed_or_publication_state(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('AI_EDITORIAL','required')
    config=tmp_path/'topics.yaml'
    config.write_text('daily:\n  editorial:\n    enabled: true\n    service_retries: 2\n')
    client=MagicMock()
    client.chat.completions.create.side_effect=timeout_error()
    with patch('pipeline.daily.collect_events',return_value=([event()],{'github:tool':'ok:1'})), \
         patch('pipeline.synthesis.get_editorial_client',return_value=client), \
         patch('pipeline.synthesis.time.sleep'),patch('pipeline.daily.write_audio') as audio:
        with pytest.raises(EditorialProviderError,match='timeout'):
            prepare(config,now=datetime(2026,9,17,12,tzinfo=timezone.utc))
    assert client.chat.completions.create.call_count==3
    audio.assert_not_called()
    assert not (tmp_path/'podcast.xml').exists()
    assert not (tmp_path/'data/state.json').exists()
    assert not (tmp_path/'.cache/publication.json').exists()


def test_production_uses_supported_sixty_second_budget():
    from pathlib import Path
    values=yaml.safe_load(Path('topics/topics.yaml').read_text(encoding='utf-8'))['daily']['editorial']
    settings=editorial_model_config(values)
    assert settings.timeout_seconds==60
    assert settings.service_retries==2
