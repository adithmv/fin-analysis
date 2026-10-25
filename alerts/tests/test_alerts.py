from datetime import datetime, timezone
from unittest.mock import MagicMock
import httpx
import pytest
from alerts.main import quiet, notify, notification_batch, check
from alerts import checks
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


def test_batch_never_acknowledges_an_incident_missing_from_message():
    rows=[dict(id=i,status="open",severity="critical",rule_key="x"*80,
               subject=str(i),message="y"*1000) for i in range(8)]
    chosen,message=notification_batch(rows)
    assert 0<len(chosen)<len(rows)
    assert len(message)<=3900
    for row in chosen:
        assert f" / {row['subject']}\n" in message


def test_disabled_source_is_explicitly_unmonitored():
    client=MagicMock()
    client.table.return_value.select.return_value.execute.return_value.data=[
        dict(source_key="disabled",enabled=False),
        dict(source_key="enabled",enabled=True,last_success_at=None,consecutive_failures=0)]
    rows=checks.sources(client,{"feed_failure_threshold":5},datetime.now(timezone.utc))
    assert rows[0]["p_status"]=="ok"
    assert rows[0]["p_detail"]["monitoring"]=="disabled"
    assert rows[1]["p_status"]=="warn"


def test_check_failure_creates_incident_and_preserves_prior_results(monkeypatch):
    client=MagicMock()
    def broken(*args):
        raise ValueError("private error")
    monkeypatch.setattr(checks,"freshness",broken)
    for name in ("sources","infrastructure","research"):
        monkeypatch.setattr(checks,name,lambda *args: [])
    monkeypatch.setattr("alerts.main.log_event",lambda *args,**kwargs:None)
    result=check(client,{"notifications_enabled":False},{})
    assert result["failed_groups"]==["broken"]
    failure=client.rpc.call_args_list[0].args[1]
    assert failure["p_rule"]=="health_check_failed" and failure["p_status"]=="fail"
    assert "private error" not in failure["p_message"]


@pytest.mark.parametrize("expected,status",[(False,"ok"),(True,"fail")])
def test_scheduler_heartbeat_is_only_required_for_enabled_pipelines(expected,status):
    client=MagicMock()
    query=MagicMock()
    client.table.return_value=query
    for method in ("select","eq","order","limit"):
        getattr(query,method).return_value=query
    query.execute.return_value.data=[]
    client.rpc.return_value.execute.return_value.data=100
    config=dict(scheduler_expected=expected,scheduler_silent_minutes=15,database_limit_bytes=1000,
        database_critical_fraction=.9,database_warning_fraction=.7,minimum_disk_free_bytes=0,backup_max_age_days=2)
    rows=checks.infrastructure(client,config,datetime.now(timezone.utc))
    assert next(r for r in rows if r["p_rule"]=="scheduler_silent")["p_status"]==status


@pytest.mark.parametrize("fails",[False,True])
def test_delivery_only_marks_incidents_after_success(monkeypatch,fails):
    client=MagicMock()
    query=MagicMock()
    client.table.return_value=query
    for method in ("select","is_","eq","order","limit","contains","update"):
        getattr(query,method).return_value=query
    row=dict(id=1,status="open",severity="critical",rule_key="disk_space",subject="local",message="Low space",meta={})
    query.execute.side_effect=[MagicMock(data=[row]),MagicMock(data=[]),MagicMock()]
    client.rpc.return_value.execute.return_value.data=True
    def send_message(message):
        if fails:
            raise RuntimeError("delivery failed")
    monkeypatch.setattr("alerts.main.send",send_message)
    monkeypatch.setattr("alerts.main.log_event",lambda *args,**kwargs:None)
    result=notify(client,dict(notifications_enabled=True,quiet_hours_ist=[22,7],minimum_notification_seconds=600),
        "run",datetime(2026,10,25,18,tzinfo=timezone.utc))
    assert result["sent"]==(0 if fails else 1)
    assert query.update.call_count==(0 if fails else 1)
