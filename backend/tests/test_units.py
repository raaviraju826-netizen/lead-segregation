"""Unit tests: parsing, extraction, classification rules, trust scoring, duplicates."""
from app.demo.dataset import DATASET
from app.demo.loader import parsed_from_case
from app.services import classifier as clf
from app.services import knowledge_base as kb
from app.services.company_trust import assess_company
from app.services.duplicates import normalize_company, normalize_email
from app.services.email_parser import parse_message
from app.services.email_trust import assess_email
from app.services.extractor import detect_injection, extract, sanitize_for_llm

CASES = {c["id"]: c for c in DATASET}


def P(cid):
    return parsed_from_case(CASES[cid])


def test_dataset_size():
    assert len(DATASET) >= 40


def test_extraction_college_signature():
    ex = extract(P("e01"))
    assert ex.company_name == "Sunrise Engineering College"
    assert ex.contact_name == "Dr. Anita Menon"
    assert ex.job_title and "Dean" in ex.job_title
    assert ex.phone == "+91 98450 11223"
    assert ex.src("company_name") == "signature"
    assert ex.requested_service and "website" in ex.requested_service.lower()


def test_free_mail_not_identity_proof():
    ex = extract(P("m07"))
    assert ex.free_mail
    assert ex.company_name == "Sharma Forgings Pvt Ltd"  # from signature, not from gmail.com
    assert ex.src("company_name") == "signature"
    ex2 = extract(P("a01"))
    assert ex2.company_name is None  # a gmail address alone never yields a company


def test_html_and_quoted_reply_handling():
    p = P("i07")
    assert "wrote:" not in p.body and "We build cloud software" not in p.body
    ex = extract(p)
    assert ex.company_name == "DevOpsWorks Solutions"


def test_forwarded_message_detected():
    p = P("f01")
    assert p.is_forwarded and "parent@gmail.com" in (p.forwarded_from or "")


def test_classify_sender_not_requested_service():
    p = P("e01")
    ex = extract(p)
    res = clf.classify(p, ex)
    assert res.industry == "Education"
    assert res.sub_industry == "Colleges and Universities"
    assert "website" in (res.interest_area or "").lower()
    assert res.industry != "IT & Software"
    assert not res.llm_used and res.method == "heuristic_rag"


def test_confidence_formula_and_thresholds():
    p = P("e01")
    res = clf.classify(p, extract(p))
    expected = round(0.6 * res.llm_confidence + 0.4 * res.retrieval_similarity, 4)
    assert abs(res.confidence - expected) < 1e-3
    assert res.decision == ("Classified" if res.confidence >= 0.75 else "Needs Review" if res.confidence >= 0.5 else res.decision)
    assert len(res.chunks) == 8  # top-8 retrieval


def test_no_evidence_is_not_guessed():
    p = P("a01")
    res = clf.classify(p, extract(p))
    assert res.industry == "Other / Unknown" and res.decision == "Other / Unknown"


def test_company_name_alone_never_classified():
    p = P("a02")  # "this is Sunrise Logistics" and nothing else
    res = clf.classify(p, extract(p))
    assert res.decision != "Classified"


def test_llm_schema_rejects_invented_industry():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        clf.LLMClassification(industry="Healthcare", confidence=0.9, reason="invented industry")
    ok = clf.LLMClassification(industry="education", confidence=0.9, reason="a college")
    assert ok.industry == "Education"


def test_prompt_injection_detected_and_stripped():
    p = P("s04")
    assert detect_injection(p.body)
    assert "IGNORE ALL PREVIOUS" not in sanitize_for_llm(p.body)
    res = clf.classify(p, extract(p))
    assert res.industry == "Logistics & Transportation"  # injection did not change the outcome
    et = assess_email(p, extract(p))
    assert any("Prompt-injection" in f for f in et["flags"])


def test_registration_never_claimed_verified():
    for cid in ("m01", "e01", "l07"):
        p = P(cid)
        ct = assess_company(p, extract(p))
        assert ct["label"] != "Verified"
        reg = next(s for s in ct["signals"] if s["name"] == "Registration evidence")
        assert reg["status"] in ("Claimed", "Unknown")
        assert "not" in ct["note"].lower() or "no " in ct["note"].lower()


def test_free_mail_not_marked_fake_and_missing_website_unknown():
    p = P("m07")
    ct = assess_company(p, extract(p))
    web = next(s for s in ct["signals"] if s["name"] == "Website consistency")
    dom = next(s for s in ct["signals"] if s["name"] == "Domain consistency")
    assert web["status"] == "Unknown" and dom["status"] == "Unknown"
    assert ct["label"] in ("Unverified", "Partially Verified")  # never an accusation


def test_conflicting_website_domain():
    p = parse_message(message_id="x", thread_id=None, from_header="A B <a@acme.com>", subject="Hi",
                      text="We manufacture bolts in our factory.\n\nRegards,\nAlan Bates\nManager\nAcme Industries Ltd\nwww.totally-different.com",
                      html=None, headers={})
    ct = assess_company(p, extract(p))
    assert ct["label"] == "Conflicting Evidence"


def test_email_auth_not_invented():
    p = P("a01")  # no headers at all
    et = assess_email(p, extract(p))
    assert et["risk"] == "Unknown"
    assert all(s["status"] == "Unknown" for s in et["signals"] if s["name"] in ("SPF", "DKIM", "DMARC"))
    # untrusted authserv is ignored
    p2 = parse_message(message_id="y", thread_id=None, from_header="A <a@acme.com>", subject="s", text="hello",
                       html=None, headers={"Authentication-Results": "evil.example; spf=pass; dkim=pass; dmarc=pass"})
    et2 = assess_email(p2, extract(p2))
    assert all(s["status"] == "Unknown" for s in et2["signals"] if s["name"] in ("SPF", "DKIM", "DMARC"))


def test_phishing_and_spoof_are_high_risk():
    for cid in ("s01", "s03", "s05"):
        p = P(cid)
        et = assess_email(p, extract(p))
        assert et["risk"] == "High", cid
        assert et["flags"]


def test_duplicate_normalisation():
    assert normalize_email("John.Doe+promo@Gmail.com") == "johndoe@gmail.com"
    assert normalize_company("Apex Auto Components Pvt. Ltd.") == normalize_company("apex auto components private limited")


def test_kb_has_industry_and_sub_metadata():
    hits = kb.retrieve("engineering college admissions students campus")
    assert hits[0]["industry"] == "Education"
    assert all(h["industry"] for h in hits)
    assert any(h["sub_industry"] for h in hits)
