from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from shared import logbook
from shared.db import bulk_upsert


@pytest.fixture
def client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(logbook, 'get_client', lambda: client)
    return client


def test_context_success_and_sanitization(client, monkeypatch):
    monkeypatch.setenv('SUPABASE_SERVICE_KEY', 'very-secret-value')
    with logbook.action(uuid4(), 'ingest', 'fetch', input_summary='very-secret-value') as ev:
        ev.output_summary = 'a\n' * 400
        ev.meta = {'access_token': 'hide', 'safe': 'very-secret-value'}
    rows = [call.args[0] for call in client.table().insert.call_args_list]
    assert [r['status'] for r in rows] == ['started', 'success']
    assert rows[1]['duration_ms'] >= 0
    assert len(rows[1]['output_summary']) <= 300
    assert rows[1]['meta'] == {'access_token': '[REDACTED]', 'safe': '[REDACTED]'}
    assert rows[0]['input_summary'] == '[REDACTED]'


def test_failure_reraises_original(client):
    with pytest.raises(RuntimeError, match='source offline'):
        with logbook.action(uuid4(), 'ingest', 'fetch'):
            raise RuntimeError('source offline')
    assert client.table().insert.call_args.args[0]['status'] == 'failed'


def test_logging_failure_does_not_crash(client, capsys):
    client.table().insert().execute.side_effect = RuntimeError('secret error')
    assert not logbook.log_event(uuid4(), 'ingest', 'fetch', 'failed')
    with logbook.action(uuid4(), 'ingest', 'fetch'):
        pass
    assert 'secret error' not in capsys.readouterr().err


def test_bulk_upsert_batches_and_propagates_errors():
    client = MagicMock()
    assert bulk_upsert(client, 'candles', [{'id': n} for n in range(5)], 'id', 2) == 5
    assert client.table().upsert.call_count == 3
    client.table().upsert().execute.side_effect = RuntimeError('db offline')
    with pytest.raises(RuntimeError):
        bulk_upsert(client, 'candles', [{'id': 0}], 'id')
