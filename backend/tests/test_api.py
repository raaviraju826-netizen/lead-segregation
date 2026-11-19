"""API tests, driven through the real pipeline on the synthetic dataset (source=demo)."""
import io

import openpyxl
import pytest

IND = {"manufacturing": "Manufacturing", "education": "Education", "it-software": "IT & Software", "logistics": "Logistics & Transportation"}


def test_health(client):
    r = client.get("/api/health").json()
    assert r["status"] == "ok" and r["llm_mode"] == "heuristic_rag" and r["knowledge_base"]["chunks"] > 10


def test_industry_filters_return_only_that_industry(client):
    for slug, name in IND.items():
        r = client.get(f"/api/leads/industry/{slug}", params={"source": "demo", "page_size": 200}).json()
        assert r["total"] > 0, slug
        assert all(i["industry"] == name for i in r["items"]), slug
        assert all(i["status"] not in ("Not a Lead", "Suspicious — Review Required") for i in r["items"])


def test_unknown_industry_404(client):
    assert client.get("/api/leads/industry/healthcare", params={"source": "demo"}).status_code == 404


def test_all_leads_filters_sort_pagination(client):
    allr = client.get("/api/leads", params={"source": "demo", "page_size": 200}).json()
    assert allr["total"] >= 40
    p1 = client.get("/api/leads", params={"source": "demo", "page_size": 10, "page": 1}).json()
    p2 = client.get("/api/leads", params={"source": "demo", "page_size": 10, "page": 2}).json()
    assert len(p1["items"]) == 10 and {i["id"] for i in p1["items"]}.isdisjoint({i["id"] for i in p2["items"]})
    pr = client.get("/api/leads", params={"source": "demo", "priority": "High", "page_size": 200}).json()
    assert pr["total"] > 0 and all(i["priority"] == "High" for i in pr["items"])
    st = client.get("/api/leads", params={"source": "demo", "status": "Suspicious — Review Required", "page_size": 200}).json()
    assert st["total"] >= 4 and all(i["status"] == "Suspicious — Review Required" for i in st["items"])
    ri = client.get("/api/leads", params={"source": "demo", "email_risk": "High", "page_size": 200}).json()
    assert all(i["email_risk"] == "High" for i in ri["items"]) and ri["total"] >= 3
    se = client.get("/api/leads", params={"source": "demo", "search": "sunrise"}).json()
    assert se["total"] >= 1 and all("sunrise" in (i["company_name"] or i["subject"] or "").lower() or "sunrise" in i["email"] for i in se["items"])
    so = client.get("/api/leads", params={"source": "demo", "sort": "relevance", "order": "desc", "page_size": 200}).json()["items"]
    assert [i["relevance_score"] for i in so] == sorted((i["relevance_score"] for i in so), reverse=True)
    assert client.get("/api/leads", params={"source": "demo", "page_size": 9999}).status_code == 422


def test_sources_are_separate(client):
    assert client.get("/api/leads", params={"source": "gmail"}).json()["total"] == 0
    assert client.get("/api/dashboard/stats", params={"source": "gmail"}).json()["total_emails"] == 0


def test_stats(client):
    s = client.get("/api/dashboard/stats", params={"source": "demo"}).json()
    assert s["total_emails"] >= 40
    assert set(s["by_industry"]) == set(IND.values())
    assert s["suspicious"] >= 4 and s["high_priority"] > 0 and s["trend"]


def test_detail_has_separate_scores_and_evidence(client):
    items = client.get("/api/leads", params={"source": "demo", "search": "Sunrise Engineering", "page_size": 5}).json()["items"]
    d = client.get(f"/api/leads/{items[0]['id']}").json()
    assert d["classification"]["retrieved_chunks"] and len(d["classification"]["retrieved_chunks"]) == 8
    assert d["company_trust"]["signals"] and d["email_trust"]["signals"] and d["lead_relevance"]["breakdown"]
    assert "extracted" in d and any(e["field"] == "company_name" for e in d["extracted"]["evidence"])
    assert client.get("/api/leads/999999").status_code == 404
    t = client.get(f"/api/leads/{items[0]['id']}/trust").json()
    assert set(t) == {"company_trust", "email_trust", "lead_relevance"}


def test_review_flow_and_validation(client):
    q = client.get("/api/review-queue", params={"source": "demo", "page_size": 50}).json()
    assert q["total"] > 0 and all(i["status"] in ("Needs Review", "Suspicious — Review Required") for i in q["items"])
    target = q["items"][0]
    bad = client.patch(f"/api/leads/{target['id']}/review", json={"industry": "Healthcare"})
    assert bad.status_code == 422
    bad2 = client.patch(f"/api/leads/{target['id']}/review", json={"industry": "Education", "sub_industry": "Warehousing"})
    assert bad2.status_code == 422
    assert client.patch(f"/api/leads/{target['id']}/review", json={}).status_code == 422
    ok = client.patch(f"/api/leads/{target['id']}/review", json={"industry": "Education", "sub_industry": "Schools", "is_genuine": True,
                                                                   "reviewer": "qa", "notes": "checked"})
    assert ok.status_code == 200
    d = ok.json()
    assert d["industry"] == "Education" and d["status"] == "Classified" and d["reviewed"] is True
    assert d["reviews"][-1]["reviewer"] == "qa" and d["reviews"][-1]["created_at"]
    assert d["classification"]["industry"] != "" # original AI output retained for audit
    q2 = client.get("/api/review-queue", params={"source": "demo", "page_size": 200}).json()
    assert target["id"] not in {i["id"] for i in q2["items"]}
    assert client.get("/api/health").json()["knowledge_base"]["reviewed_examples"] >= 1
    # mark irrelevant
    other = q2["items"][0]["id"]
    r = client.patch(f"/api/leads/{other}/review", json={"is_genuine": False}).json()
    assert r["status"] == "Not a Lead"


def test_unreviewed_ai_output_not_in_rag_examples(client):
    from app.services import knowledge_base as kb
    n = kb.kb_status()["reviewed_examples"]
    total = client.get("/api/leads", params={"source": "demo", "page_size": 200}).json()["total"]
    assert n < total  # only reviewer-confirmed rows are stored


def test_duplicates_flagged_not_merged(client):
    dups = client.get("/api/duplicates").json()
    assert dups, "similar-name / different-domain candidate expected"
    d = dups[0]
    assert d["company"]["id"] != d["other_company"]["id"]  # flagged, not auto-merged


def test_export_excel(client):
    r = client.get("/api/export/excel", params={"source": "demo"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/vnd.openxmlformats")
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Summary", "All Leads", "Manufacturing", "Education", "IT & Software", "Logistics & Transportation",
                             "Needs Review", "Suspicious — Review Required"]
    for name in ("Manufacturing", "Education", "IT & Software", "Logistics & Transportation"):
        ws = wb[name]
        col = [c.value for c in ws[1]].index("Industry")
        vals = {row[col].value for row in ws.iter_rows(min_row=2)}
        assert vals == {name}, name
        assert ws.auto_filter.ref and ws.freeze_panes == "A2"
    assert wb["Summary"]["A1"].value == "Metric"
    assert [c.value for c in wb["All Leads"][1]][:3] == ["Company Name", "Contact Name", "Email"]
    one = openpyxl.load_workbook(io.BytesIO(client.get("/api/export/excel", params={"source": "demo", "industry": "education"}).content))
    assert one.sheetnames == ["Summary", "Education"]


def test_export_csv(client):
    r = client.get("/api/export/csv", params={"source": "demo", "industry": "logistics"})
    assert r.status_code == 200 and "text/csv" in r.headers["content-type"]
    lines = r.text.strip().splitlines()
    assert len(lines) > 1 and all("Logistics & Transportation" in l for l in lines[1:])
    assert client.get("/api/export/csv", params={"industry": "nope"}).status_code == 404


def test_gmail_status_unconfigured_is_honest(client):
    s = client.get("/api/gmail/status").json()
    assert s["connected"] is False and s["configured"] is False and s["configuration_problem"]
    assert s["connected_account"] is None


def test_gmail_sync_fails_cleanly_when_not_connected(client):
    r = client.post("/api/gmail/sync")
    assert r.status_code in (400, 401)
    assert "detail" in r.json()
    h = client.get("/api/gmail/syncs").json()
    assert h and h[0]["status"] == "failed"


def test_api_key_enforced(monkeypatch, client):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "api_access_key", "secret")
    assert client.get("/api/leads", params={"source": "demo"}).status_code == 401
    assert client.get("/api/leads", params={"source": "demo"}, headers={"X-API-Key": "secret"}).status_code == 200
    assert client.get("/api/health").status_code == 200


def test_demo_clear_and_reload(client):
    assert client.delete("/api/demo").json()["deleted"] >= 40
    assert client.get("/api/leads", params={"source": "demo"}).json()["total"] == 0
    assert client.post("/api/demo/load").json()["loaded"] >= 40
