from datetime import datetime, timezone
from unittest.mock import MagicMock
import httpx
import pytest
from alerts.main import quiet, notify
from alerts.notifiers.telegram import send


def test_quiet_hours_use_india_time():
    assert quiet(datetime(2026,10,24,18,tzinfo=timezone.utc),[22,7])
    assert not quiet(datetime(2026,10,24,9,tzinfo=timezone.utc),[22,7])


def test_disabled_notifications_never_touch_network_or_database():
    client=MagicMock()
    assert notify(client,{"notifications_enabled":False},"run",datetime.now(timezone.utc))["sent"]==0
    client.table.assert_not_called()


def test_telegram_error_never_exposes_token(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN","123:secretTokenValue")
    monkeypatch.setenv("TELEGRAM_CHAT_ID","456")
    client=httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(429,json={"ok":False})))
    with pytest.raises(RuntimeError) as error:
        send("Test",client)
    assert "secretTokenValue" not in str(error.value)


def test_telegram_is_plain_text_and_never_paid(monkeypatch):
    import json
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN","123:secretTokenValue")
    monkeypatch.setenv("TELEGRAM_CHAT_ID","456")
    def handler(request):
        body=json.loads(request.content)
        assert body["allow_paid_broadcast"] is False
        assert "parse_mode" not in body and body["protect_content"] is True
        assert len(body["text"])==3900
        return httpx.Response(200,json={"ok":True})
    send("x"*5000,httpx.Client(transport=httpx.MockTransport(handler)))
