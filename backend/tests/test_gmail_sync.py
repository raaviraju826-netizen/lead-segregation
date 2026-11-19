"""Gmail ingestion tests using a fake Gmail layer (no network, no credentials)."""
import base64

from app.services import gmail
from app.services.email_parser import parse_gmail_api_message


def b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


def gmsg(mid, frm, subject, text, html=None, attachments=()):
    parts = [{"mimeType": "text/plain", "body": {"data": b64(text)}}]
    if html:
        parts.append({"mimeType": "text/html", "body": {"data": b64(html)}})
    for a in attachments:
        parts.append({"mimeType": "application/pdf", "filename": a, "body": {"size": 10, "attachmentId": "x"}})
    return {"id": mid, "threadId": "t-" + mid, "internalDate": "1793000000000", "payload": {
        "mimeType": "multipart/alternative", "parts": parts,
        "headers": [{"name": "From", "value": frm}, {"name": "Subject", "value": subject}, {"name": "Date", "value": "Mon, 2 Nov 2026 10:00:00 +0000"},
                    {"name": "Authentication-Results", "value": "mx.google.com; spf=pass smtp.mailfrom=x.com; dkim=pass; dmarc=pass"}]}}


MSGS = {
    "g1": gmsg("g1", "Ravi Menon <ravi@steelworks.com>", "ERP enquiry",
               "We are a steel manufacturing company with a fabrication plant. We need an ERP for inventory.\n\nRegards,\nRavi Menon\nHead of IT\nSteelworks Industries Pvt Ltd\n+91 98100 55555"),
    "g2": gmsg("g2", "Admissions <adm@oakuniv.edu.in>", "Portal", "Our university campus has 5000 students. We are looking for an admissions portal.\n\nRegards,\nLata Rao\nRegistrar\nOak University"),
    "g3": gmsg("g3", "Fresh <fresh@newlogistics.com>", "Fleet app", "We are a courier and freight logistics company. We need a driver mobile app.\n\nRegards,\nSam Fox\nCTO\nNew Logistics Ltd"),
}


def fake_gmail(monkeypatch, listing, history_ids=None, mismatch=False):
    calls = {"full": 0, "inc": 0}

    def verified():
        if mismatch:
            raise gmail.AccountMismatch("other@gmail.com", "target@gmail.com")
        return object(), {"emailAddress": "target@gmail.com", "historyId": "500"}

    monkeypatch.setattr(gmail, "get_verified_service", verified)
    monkeypatch.setattr(gmail, "list_inbox_ids", lambda svc, n: calls.__setitem__("full", calls["full"] + 1) or list(listing))
    monkeypatch.setattr(gmail, "list_new_ids", lambda svc, start: calls.__setitem__("inc", calls["inc"] + 1) or history_ids)
    monkeypatch.setattr(gmail, "get_message", lambda svc, mid: MSGS[mid])
    return calls


def test_parse_gmail_payload_with_attachments():
    m = gmsg("p1", "A B <a@b.com>", "Hi", "plain body", html="<p>html body</p>", attachments=["a.pdf"])
    p = parse_gmail_api_message(m)
    assert p.sender_email == "a@b.com" and p.body == "plain body" and p.html_present
    assert p.attachments[0]["filename"] == "a.pdf" and p.date.year == 2026


def test_full_then_incremental_sync(client, monkeypatch):
    from app.services.sync import run_gmail_sync
    calls = fake_gmail(monkeypatch, ["g1", "g2"], history_ids=None)
    s1 = run_gmail_sync("manual")
    assert s1.status == "success" and s1.mode == "full" and s1.fetched == 2 and s1.processed == 2
    leads = client.get("/api/leads", params={"source": "gmail", "page_size": 50}).json()
    assert leads["total"] == 2
    assert {i["industry"] for i in leads["items"]} == {"Manufacturing", "Education"}
    # incremental: history returns one already-seen and one new message
    calls = fake_gmail(monkeypatch, [], history_ids=["g2", "g3"])
    s2 = run_gmail_sync("manual")
    assert s2.mode == "incremental" and s2.fetched == 2 and s2.processed == 1  # g2 not reprocessed
    assert client.get("/api/leads", params={"source": "gmail"}).json()["total"] == 3
    # re-running with nothing new processes nothing
    fake_gmail(monkeypatch, [], history_ids=["g1", "g2", "g3"])
    assert run_gmail_sync("manual").processed == 0


def test_status_shows_last_sync(client):
    s = client.get("/api/gmail/status").json()
    assert s["last_sync_at"] and s["last_sync"]["status"] == "success"


def test_wrong_account_is_rejected(client, monkeypatch):
    fake_gmail(monkeypatch, ["g1"], mismatch=True)
    before = client.get("/api/leads", params={"source": "gmail"}).json()["total"]
    r = client.post("/api/gmail/sync")
    assert r.status_code == 403 and "does not match" in r.json()["detail"]
    assert client.get("/api/leads", params={"source": "gmail"}).json()["total"] == before


def test_only_readonly_scope():
    assert gmail.SCOPES == ["https://www.googleapis.com/auth/gmail.readonly"]
