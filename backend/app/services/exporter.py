from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from .. import repository as repo
from .taxonomy import industry_by_slug, industry_names

COLUMNS = [
    ("company_name", "Company Name"), ("contact_name", "Contact Name"), ("email", "Email"), ("phone", "Phone"), ("website", "Website"),
    ("industry", "Industry"), ("sub_industry", "Sub-industry"), ("interest_area", "Interest Area"),
    ("company_trust_score", "Company Trust Score"), ("company_trust_label", "Company Trust Label"),
    ("email_trust_score", "Email Trust Score"), ("email_risk", "Email Risk"),
    ("relevance_score", "Lead Relevance Score"), ("priority", "Lead Priority"), ("confidence", "Classification Confidence"),
    ("status", "Status"), ("lead_type", "Lead Type"), ("reason", "Reason"), ("subject", "Subject"), ("email_date", "Email Date"),
]
NEEDS_REVIEW_SHEET = "Needs Review"
SUSPICIOUS_SHEET = "Suspicious — Review Required"
HEADER_FILL = PatternFill("solid", start_color="1E3A8A")


def _safe(v):
    """Neutralise spreadsheet formula injection from untrusted email-derived text."""
    return "'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r") else v


def _rows_table(rows: list[dict]) -> tuple[list[str], list[list]]:
    headers = [label for _, label in COLUMNS]
    out: list[list] = []
    for r in rows:
        row_vals = []
        for key, label in COLUMNS:
            v = _safe(r.get(key))
            if label == "Email Date" and v is not None:
                v = str(v).replace("T", " ")[:16]
            elif label == "Classification Confidence" and v is not None:
                try:
                    v = round(float(v), 2)
                except Exception:
                    pass
            row_vals.append(v)
        out.append(row_vals)
    return headers, out


def _style_sheet(ws, headers: list[str], data_rows: list[list]) -> None:
    ws.freeze_panes = "A2"
    ws.append(headers)
    for r in data_rows:
        ws.append(r)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = HEADER_FILL
        c.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 30
    if ws.max_row >= 1 and ws.max_column >= 1:
        ws.auto_filter.ref = ws.dimensions
    for i, col in enumerate(headers, start=1):
        sample_vals = [str(r[i - 1]) for r in data_rows[:500] if i - 1 < len(r) and r[i - 1] is not None]
        width = max([len(str(col))] + [len(v) for v in sample_vals]) + 2
        ws.column_dimensions[get_column_letter(i)].width = min(max(width, 12), 60)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=(ws.cell(1, c.column).value in ("Reason", "Subject")))


def build_excel(db: Session, source: str, industry: str | None = None) -> bytes:
    rows = [repo.summary(e) for e in repo.all_emails(db, source=source)]
    leads = [r for r in rows if r["status"] not in (repo.NOT_LEAD, repo.SUSPICIOUS)]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    summary_rows = [[_safe(k), _safe(v)] for k, v in [
        ("Report generated", now),
        ("Data source", "Gmail (real)" if source == "gmail" else "DEMO MODE (synthetic emails)"),
        ("Total emails processed", len(rows)),
        ("Total business leads", len(leads)),
        *[(f"{n} leads", sum(1 for r in leads if r["industry"] == n)) for n in industry_names()],
        ("Needs Review", sum(r["status"] == "Needs Review" for r in rows)),
        (SUSPICIOUS_SHEET, sum(r["status"] == repo.SUSPICIOUS for r in rows)),
        ("High-priority leads", sum(r["priority"] == "High" for r in leads)),
        ("Note", "Scores are preliminary, evidence-based assessments; not legal verification."),
    ]]
    wb = Workbook()
    ws_sum = wb.active
    ws_sum.title = "Summary"
    _style_sheet(ws_sum, ["Metric", "Value"], summary_rows)
    ws_sum.column_dimensions["A"].width = 30
    ws_sum.column_dimensions["B"].width = 70

    sheets: list[tuple[str, list[dict]]] = []
    if industry:
        ind = industry_by_slug(industry)
        name = ind["name"] if ind else industry
        sheets.append((name[:31], [r for r in leads if r["industry"] == name]))
    else:
        sheets.append(("All Leads", rows))
        for n in industry_names():
            sheets.append((n[:31], [r for r in leads if r["industry"] == n]))
        sheets.append((NEEDS_REVIEW_SHEET, [r for r in rows if r["status"] == "Needs Review"]))
        sheets.append((SUSPICIOUS_SHEET, [r for r in rows if r["status"] == repo.SUSPICIOUS]))

    for sname, srows in sheets:
        ws = wb.create_sheet(title=sname)
        hdrs, drows = _rows_table(srows)
        _style_sheet(ws, hdrs, drows)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_csv(db: Session, source: str, industry: str | None = None) -> str:
    if industry:
        emails = repo.all_emails(db, source=source, industry=industry, only_leads=True)
    else:
        emails = repo.all_emails(db, source=source)
    hdrs, drows = _rows_table([repo.summary(e) for e in emails])
    sio = io.StringIO()
    writer = csv.writer(sio)
    writer.writerow(hdrs)
    for r in drows:
        writer.writerow(["" if v is None else v for v in r])
    return sio.getvalue()
