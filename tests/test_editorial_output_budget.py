"""Offline output-ceiling and fail-closed truncation regressions."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import yaml

from pipeline.models_client import EditorialProviderError
from pipeline.synthesis import refine_editorial
from tests.test_grounded_editorial import approval, base_story, draft, event, manifest, response


def production_config():
    return yaml.safe_load(Path('topics/topics.yaml').read_text(encoding='utf-8'))['daily']['editorial']


def test_production_draft_ceiling_keeps_verification_and_retry_limits():
    config = production_config()
    proposal = draft()
    client = MagicMock()
    client.chat.completions.create.side_effect = [response(proposal), response(approval(proposal))]
    with patch('pipeline.synthesis.get_editorial_client', return_value=client):
        stories, generation = refine_editorial([event()], [base_story([event()])], [], config=config)
    calls = client.chat.completions.create.call_args_list
    assert [call.kwargs['max_tokens'] for call in calls] == [6000, 2500]
    assert config['service_retries'] == 2
    assert all(call.kwargs['reasoning_effort'] == 'low' for call in calls)
    assert generation['calls'] == 2
    manifest(stories, generation).validate(require_audio=False)


@pytest.mark.parametrize('stage', ['draft', 'verify'])
@pytest.mark.parametrize('usage', [None, SimpleNamespace(prompt_tokens=10000, completion_tokens=6000,
    completion_tokens_details=SimpleNamespace(reasoning_tokens=1024))])
def test_length_never_retries_accepts_partial_json_or_skips_verification(stage, usage, caplog):
    proposal = draft()
    truncated = response(proposal, finish_reason='length')  # Even valid JSON is not complete.
    truncated.usage = usage
    client = MagicMock()
    client.chat.completions.create.side_effect = ([truncated] if stage == 'draft'
        else [response(proposal), truncated])
    with patch('pipeline.synthesis.get_editorial_client', return_value=client), \
         patch('pipeline.synthesis.time.sleep') as delay:
        with pytest.raises(EditorialProviderError, match='finish_reason=length'):
            refine_editorial([event()], [base_story([event()])], [], config=production_config())
    assert client.chat.completions.create.call_count == (1 if stage == 'draft' else 2)
    delay.assert_not_called()
    assert f"max_output_tokens={6000 if stage == 'draft' else 2500}" in caplog.text
    assert proposal['opening'] not in caplog.text
    if usage:
        assert "'completion_tokens': 6000" in caplog.text
        assert "'reasoning_tokens': 1024" in caplog.text


def test_truncation_diagnostics_ignore_untrusted_counter_values(caplog):
    truncated = response(draft(), finish_reason='length')
    truncated.usage = SimpleNamespace(prompt_tokens='PRIVATE_VALUE', completion_tokens=True,
        completion_tokens_details=SimpleNamespace(reasoning_tokens=-1))
    client = MagicMock()
    client.chat.completions.create.return_value = truncated
    with patch('pipeline.synthesis.get_editorial_client', return_value=client):
        with pytest.raises(EditorialProviderError):
            refine_editorial([event()], [base_story([event()])], [], config=production_config())
    assert 'PRIVATE_VALUE' not in caplog.text
    assert 'usage={}' in caplog.text
