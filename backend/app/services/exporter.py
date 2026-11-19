from __future__ import annotations

import io
from datetime import datetime, timezone

import pandas as pd
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


def _frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame([{label: _safe(r.get(key)) for key, label in COLUMNS} for r in rows], columns=[l for _, l in COLUMNS])
    if "Email Date" in df and len(df):
        df["Email Date"] = df["Email Date"].astype(str).str.replace("T", " ").str.slice(0, 16)
    if "Classification Confidence" in df and len(df):
        df["Classification Confidence"] = df["Classification Confidence"].astype(float).round(2)
    return df


def _style(ws, df: pd.DataFrame) -> None:
    ws.freeze_panes = "A2"
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = HEADER_FILL
        c.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 30
    if ws.max_row >= 1 and ws.max_column >= 1:
        ws.auto_filter.ref = ws.dimensions
    for i, col in enumerate(df.columns, start=1):
        width = max([len(str(col))] + [len(str(v)) for v in df[col].head(500)]) + 2
        ws.column_dimensions[get_column_letter(i)].width = min(max(width, 12), 60)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=(ws.cell(1, c.column).value in ("Reason", "Subject")))


def build_excel(db: Session, source: str, industry: str | None = None) -> bytes:
    rows = [repo.summary(e) for e in repo.all_emails(db, source=source)]
    leads = [r for r in rows if r["status"] not in (repo.NOT_LEAD, repo.SUSPICIOUS)]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    summary_rows = [("Report generated", now), ("Data source", "Gmail (real)" if source == "gmail" else "DEMO MODE (synthetic emails)"),
                    ("Total emails processed", len(rows)), ("Total business leads", len(leads))]
    for n in industry_names():
        summary_rows.append((f"{n} leads", sum(1 for r in leads if r["industry"] == n)))
    summary_rows += [("Needs Review", sum(r["status"] == "Needs Review" for r in rows)),
                     (SUSPICIOUS_SHEET, sum(r["status"] == repo.SUSPICIOUS for r in rows)),
                     ("High-priority leads", sum(r["priority"] == "High" for r in leads)),
                     ("Note", "Scores are preliminary, evidence-based assessments; not legal verification.")]
    sheets: list[tuple[str, pd.DataFrame]] = []
    if industry:
        ind = industry_by_slug(industry)
        name = ind["name"] if ind else industry
        sheets.append((name[:31], _frame([r for r in leads if r["industry"] == name])))
    else:
        sheets.append(("All Leads", _frame(rows)))
        for n in industry_names():
            sheets.append((n[:31], _frame([r for r in leads if r["industry"] == n])))
        sheets.append((NEEDS_REVIEW_SHEET, _frame([r for r in rows if r["status"] == "Needs Review"])))
        sheets.append((SUSPICIOUS_SHEET, _frame([r for r in rows if r["status"] == repo.SUSPICIOUS])))
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame(summary_rows, columns=["Metric", "Value"]).to_excel(xw, sheet_name="Summary", index=False)
        for name, df in sheets:
            df.to_excel(xw, sheet_name=name, index=False)
        _style(xw.sheets["Summary"], pd.DataFrame(summary_rows, columns=["Metric", "Value"]))
        xw.sheets["Summary"].column_dimensions["A"].width = 30
        xw.sheets["Summary"].column_dimensions["B"].width = 70
        for name, df in sheets:
            _style(xw.sheets[name], df)
    return buf.getvalue()


def build_csv(db: Session, source: str, industry: str | None = None) -> str:
    if industry:
        ind = industry_by_slug(industry)
        emails = repo.all_emails(db, source=source, industry=industry, only_leads=True)
    else:
        emails = repo.all_emails(db, source=source)
    return _frame([repo.summary(e) for e in emails]).to_csv(index=False)
