"""Evaluation harness. Runs the real pipeline on the synthetic dataset in an isolated temp DB / vector store and
reports MEASURED metrics only. Usage (from project root):  backend/.venv/bin/python -m backend.evaluation.run_eval
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="leadsense_eval_")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/eval.db"
os.environ["CHROMA_DIR"] = f"{_tmp}/chroma"
if "--llm" not in sys.argv:
    os.environ["OPENAI_API_KEY"] = ""  # measure the offline heuristic+RAG mode unless --llm is passed

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal, init_db  # noqa: E402
from app.demo.dataset import DATASET, IND_E, IND_I, IND_L, IND_M, OTHER  # noqa: E402
from app.demo.loader import load_demo  # noqa: E402
from app.models import DuplicateCandidate, Email  # noqa: E402
from app.services import knowledge_base as kb  # noqa: E402

LABELS = [IND_M, IND_E, IND_I, IND_L, OTHER]


def norm(s):
    return (s or "").lower().strip(" .,")


def main() -> dict:
    init_db()
    kb.ensure_knowledge_base()
    db = SessionLocal()
    t0 = time.perf_counter()
    load_demo(db)
    total_s = time.perf_counter() - t0
    emails = {e.gmail_message_id.removeprefix("demo-"): e for e in db.scalars(select(Email))}
    cases = {c["id"]: c for c in DATASET}

    conf = defaultdict(Counter)
    ind_total = ind_ok = 0
    sub_total = sub_ok = sub_general = 0
    ext = {"company": [0, 0], "contact": [0, 0], "phone": [0, 0]}
    status_ok = status_total = type_ok = type_total = 0
    bins = {"<0.50": [0, 0], "0.50-0.75": [0, 0], ">=0.75": [0, 0]}
    failures: list[dict] = []
    for cid, case in cases.items():
        e, exp = emails[cid], case["expected"]
        cls = e.classification
        if exp.get("industry", "x") is not None and "industry" in exp:
            ind_total += 1
            ok = e.industry == exp["industry"]
            ind_ok += ok
            conf[exp["industry"]][e.industry] += 1
            b = "<0.50" if cls.confidence < 0.5 else "0.50-0.75" if cls.confidence < 0.75 else ">=0.75"
            if exp["industry"] != OTHER:
                bins[b][0] += 1
                bins[b][1] += ok
            if not ok:
                failures.append({"id": cid, "field": "industry", "expected": exp["industry"], "got": e.industry, "conf": cls.confidence})
        if exp.get("sub"):
            sub_total += 1
            sub_ok += e.sub_industry == exp["sub"]
            sub_general += e.sub_industry == "General"
            if e.sub_industry != exp["sub"]:
                failures.append({"id": cid, "field": "sub_industry", "expected": exp["sub"], "got": e.sub_industry})
        for key, got in (("company", e.company.name if e.company else None), ("contact", e.contact.name if e.contact else None),
                         ("phone", e.contact.phone if e.contact else None)):
            if exp.get(key):
                ext[key][0] += 1
                ok = norm(got) == norm(exp[key])
                ext[key][1] += ok
                if not ok:
                    failures.append({"id": cid, "field": key, "expected": exp[key], "got": got})
        st = exp.get("status")
        grp = exp.get("group")
        if st or grp:
            status_total += 1
            if st:
                ok = e.status in st
            elif grp == "not_lead":
                ok = e.status == "Not a Lead"
            elif grp == "suspicious":
                ok = e.status == "Suspicious — Review Required"
            else:
                ok = e.status not in ("Not a Lead", "Suspicious — Review Required")
            status_ok += ok
            if not ok:
                failures.append({"id": cid, "field": "status", "expected": st or grp, "got": e.status})
        if exp.get("type"):
            type_total += 1
            type_ok += e.lead_type == exp["type"]
            if e.lead_type != exp["type"]:
                failures.append({"id": cid, "field": "lead_type", "expected": exp["type"], "got": e.lead_type})

    per_label = {}
    for lab in LABELS:
        tp = conf[lab][lab]
        fp = sum(conf[o][lab] for o in LABELS if o != lab)
        fn = sum(conf[lab][o] for o in LABELS if o != lab)
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        per_label[lab] = {"precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0, "support": tp + fn}
    macro_f1 = round(statistics.mean(v["f1"] for v in per_label.values()), 3)

    # duplicates
    dup_total = dup_ok = 0
    cand_emails = {d.email_id for d in db.scalars(select(DuplicateCandidate))}
    for cid, case in cases.items():
        exp = case["expected"]
        if exp.get("duplicate_company_of"):
            dup_total += 1
            dup_ok += emails[cid].company_id == emails[exp["duplicate_company_of"]].company_id and emails[cid].company_id is not None
        if exp.get("duplicate_candidate"):
            dup_total += 1
            dup_ok += emails[cid].id in cand_emails and emails[cid].company_id != emails["m01"].company_id

    # prompt-injection safety: s04 must stay logistics and not be 'verified'/auto-classified-as-education
    inj = emails["s04"]
    times = [e.processing_ms or 0 for e in emails.values()]
    res = {
        "mode": "llm_rag" if "--llm" in sys.argv else "heuristic_rag (offline, no LLM)",
        "emails": len(cases),
        "industry": {"labelled": ind_total, "accuracy": round(ind_ok / ind_total, 3), "goal": 0.85, "macro_f1": macro_f1, "per_label": per_label,
                     "confusion_matrix": {"labels": LABELS, "rows": [[conf[a][b] for b in LABELS] for a in LABELS]}},
        "sub_industry": {"labelled": sub_total, "accuracy": round(sub_ok / sub_total, 3), "goal": 0.75, "returned_general": sub_general},
        "extraction_accuracy": {k: {"n": v[0], "accuracy": round(v[1] / v[0], 3) if v[0] else None} for k, v in ext.items()},
        "status_handling_accuracy": {"n": status_total, "accuracy": round(status_ok / status_total, 3)},
        "lead_type_accuracy": {"n": type_total, "accuracy": round(type_ok / type_total, 3)},
        "duplicate_detection": {"n": dup_total, "correct": dup_ok},
        "confidence_calibration": {k: {"n": v[0], "industry_accuracy": round(v[1] / v[0], 3) if v[0] else None} for k, v in bins.items()},
        "prompt_injection_case": {"industry": inj.industry, "status": inj.status, "company_trust_label": inj.company_trust.label},
        "processing_ms": {"mean": round(statistics.mean(times), 1), "p95": sorted(times)[int(0.95 * len(times)) - 1], "total_seconds": round(total_s, 2)},
        "failures": failures,
    }
    out = Path(__file__).parent / "results.json"
    out.write_text(json.dumps(res, indent=2))
    print(json.dumps({k: v for k, v in res.items() if k != "failures"}, indent=2))
    print("\nFAILURES:")
    for f in failures:
        print(f)
    return res


if __name__ == "__main__":
    main()
