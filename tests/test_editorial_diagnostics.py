import logging
from unittest.mock import MagicMock, patch

import pytest

from pipeline.models_client import EditorialProviderError
from pipeline.synthesis import _request_editorial, refine_editorial
from tests.test_editorial_timeout import timeout_error
from tests.test_grounded_editorial import approval, base_story, draft, event, response


def test_attempt_logs_distinguish_stages_and_preserve_verification(caplog):
    proposal = draft()
    client = MagicMock()
    unavailable = RuntimeError('SECRET source text token')
    unavailable.status_code = 503
    client.chat.completions.create.side_effect = [unavailable, response(proposal), timeout_error(), response(approval(proposal))]
    with caplog.at_level(logging.INFO, logger='pipeline.synthesis'), patch('pipeline.synthesis.get_editorial_client', return_value=client), patch('pipeline.synthesis.time.sleep'):
        _, generation = refine_editorial([event()], [base_story([event()])], [], config={'service_retries': 2})
    assert generation['verified'] and generation['request_attempts'] == 4
    assert 'stage=draft attempt=1/3 category=http_503' in caplog.text
    assert 'stage=verify attempt=1/3 category=timeout' in caplog.text
    assert 'stage=verify attempt=2/3' in caplog.text
    assert 'SECRET' not in caplog.text
    assert 'chat/completions' not in caplog.text


@pytest.mark.parametrize('status,reason,attempts', [(503, 'attempts_exhausted', 3), (401, 'nonretryable', 1), ('SECRET', 'nonretryable', 1)])
def test_terminal_logs_are_safe_and_keep_attempt_ceiling(caplog, status, reason, attempts):
    error = RuntimeError('SECRET credential response')
    error.status_code = status
    client = MagicMock()
    client.chat.completions.create.side_effect = error
    with caplog.at_level(logging.INFO, logger='pipeline.synthesis'), patch('pipeline.synthesis.time.sleep'):
        with pytest.raises(EditorialProviderError):
            _request_editorial(client, model='gemini-3.8-flash', instructions='SECRET', payload={'secret': 'SECRET'}, max_input_chars=2000, max_output_tokens=4000, timeout=60, service_retries=2, stage='SECRET')
    assert client.chat.completions.create.call_count == attempts
    assert f'stage=request reason={reason}' in caplog.text
    assert 'SECRET' not in caplog.text


def test_deadline_logs_do_not_claim_an_unstarted_attempt(caplog):
    client = MagicMock()
    with caplog.at_level(logging.INFO, logger='pipeline.synthesis'), patch('pipeline.synthesis.time.monotonic', return_value=20):
        with pytest.raises(EditorialProviderError, match='time budget exhausted'):
            _request_editorial(client, model='gemini-3.8-flash', instructions='Evidence', payload={}, max_input_chars=2000, max_output_tokens=4000, timeout=60, deadline=20, stage='draft')
    client.chat.completions.create.assert_not_called()
    assert 'stage=draft reason=budget_before_attempt' in caplog.text
    assert 'attempt=1' not in caplog.text
