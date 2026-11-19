"""Tests for CSV/EML/MSG/MBOX upload, direct email ingestion, batch tracking, stats, and industry config APIs."""
from __future__ import annotations

import json


def test_csv_upload_with_flexible_column_mapping(client):
    csv_content = (
        "AuthorName,SenderMail,MailTitle,MailContent,ReceivedTime\n"
        "Dr. Ramesh Babu,ramesh@nitcampus.edu.in,Campus ERP Proposal,"
        "\"We are an engineering college with 4,000 students on campus. We need a custom ERP and admissions portal. "
        "Regards, Dr. Ramesh Babu, Dean, NIT Campus College, +91 98450 22334\",2026-11-10T09:30:00Z\n"
        "Kiran Desai,kiran@ precisiongear.co.in,CNC machine IoT dashboard,"
        "\"We manufacture industrial machinery and CNC gears in our Pune factory. Looking for an IoT analytics dashboard. "
        "Regards, Kiran Desai, Plant Head, Precision Gear Works Pvt Ltd\",2026-11-11T10:15:00Z\n"
    )
    mapping = {
        "sender_name": "AuthorName",
        "sender_email": "SenderMail",
        "subject": "MailTitle",
        "body": "MailContent",
        "received_at": "ReceivedTime",
    }
    res = client.post(
        "/api/uploads",
        files={"file": ("leads_custom.csv", csv_content.encode("utf-8"), "text/csv")},
        data={"column_mapping": json.dumps(mapping), "source": "upload"},
    )
    assert res.status_code == 200, res.text
    batch = res.json()
    assert batch["file_type"] == "csv"
    assert batch["total_records"] == 2
    assert batch["processed_records"] == 2
    assert batch["column_mapping"]["sender_email"] == "SenderMail"

    # Verify batch retrieval
    b2 = client.get(f"/api/batches/{batch['id']}").json()
    assert b2["id"] == batch["id"] and len(b2["email_ids"]) == 2

    # Verify uploaded leads are stored and classified properly
    leads = client.get("/api/leads", params={"source": "upload"}).json()
    assert leads["total"] >= 2
    industries = {item["industry"] for item in leads["items"]}
    assert "Education" in industries and "Manufacturing" in industries


def test_eml_mbox_and_msg_uploads(client):
    eml_bytes = (
        b"From: Vikram Sethi <vikram@swiftfreight.in>\r\n"
        b"Subject: Warehouse & Fleet software quote\r\n"
        b"Date: Wed, 12 Nov 2026 11:00:00 +0000\r\n"
        b"Message-ID: <eml-test-101@swiftfreight.in>\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"Hello,\r\nWe are a freight transportation and warehousing company operating 120 trucks. "
        b"We need fleet tracking software.\r\n\r\nRegards,\r\nVikram Sethi\r\nDirector\r\nSwiftFreight Logistics Pvt Ltd\r\n"
    )
    r_eml = client.post("/api/uploads", files={"file": ("enquiry.eml", eml_bytes, "message/rfc822")})
    assert r_eml.status_code == 200 and r_eml.json()["processed_records"] == 1

    mbox_bytes = (
        b"From cloud@saasbuilder.io Thu Nov 13 12:00:00 2026\n"
        b"From: Neha Gupta <neha@saasbuilder.io>\n"
        b"Subject: DevOps & Cloud Partnership\n"
        b"Message-ID: <mbox-test-202@saasbuilder.io>\n\n"
        b"Hi,\nWe are a SaaS and custom software development company. We want to explore a partnership on cloud migration.\n"
        b"Regards,\nNeha Gupta\nCTO\nSaaSBuilder Technologies Pvt Ltd\n"
    )
    r_mbox = client.post("/api/uploads", files={"file": ("archive.mbox", mbox_bytes, "application/mbox")})
    assert r_mbox.status_code == 200 and r_mbox.json()["processed_records"] == 1

    r_msg = client.post("/api/uploads", files={"file": ("outlook.msg", eml_bytes.replace(b"eml-test-101", b"msg-test-303"), "application/vnd.ms-outlook")})
    assert r_msg.status_code == 200 and r_msg.json()["processed_records"] == 1


def test_direct_email_ingest_and_industry_patch(client):
    r = client.post(
        "/api/emails/ingest",
        json={
            "source": "upload",
            "sender_name": "Prof. Alok Sharma",
            "sender_email": "alok@globaledtech.in",
            "subject": "Mobile app for our online learning platform",
            "body": "We are an EdTech company running online courses for 50,000 students. We need a mobile app for learners.",
        },
    )
    assert r.status_code == 200
    batch = r.json()
    lead_id = batch["email_ids"][0]

    # Patch industry using the Education & EdTech alias via PATCH /api/leads/{id}/industry
    patched = client.patch(
        f"/api/leads/{lead_id}/industry",
        json={"industry": "Education & EdTech", "sub_industry": "EdTech Platforms", "reviewer": "qa_lead"},
    )
    assert patched.status_code == 200
    data = patched.json()
    assert data["industry"] == "Education"
    assert data["sub_industry"] == "EdTech Platforms"
    assert data["status"] == "Classified"


def test_stats_exports_and_duplicate_logs(client):
    st = client.get("/api/stats", params={"source": "all"}).json()
    assert st["total_emails"] >= 45
    assert st["unique_companies"] > 10
    assert "duplicate_records" in st and "not_a_lead" in st
    assert "by_sub_industry" in st and "confidence_distribution" in st

    logs = client.get("/api/duplicates/logs").json()
    assert isinstance(logs, list) and len(logs) > 0

    r_csv = client.get("/api/exports/csv", params={"source": "upload"})
    assert r_csv.status_code == 200 and "Company Name" in r_csv.text
    r_xlsx = client.get("/api/exports/excel", params={"source": "upload"})
    assert r_xlsx.status_code == 200 and r_xlsx.headers["content-type"].startswith("application/vnd.openxmlformats")
