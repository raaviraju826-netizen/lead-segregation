from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from ..config import CONFIG_DIR

INDUSTRY_ALIASES = {
    "education & edtech": "Education",
    "education and edtech": "Education",
    "education-edtech": "Education",
    "it & software": "IT & Software",
    "it and software": "IT & Software",
    "logistics & transportation": "Logistics & Transportation",
    "logistics and transportation": "Logistics & Transportation",
}


@lru_cache
def load_taxonomy() -> dict[str, Any]:
    with open(CONFIG_DIR / "industries.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_taxonomy(data: dict[str, Any]) -> None:
    with open(CONFIG_DIR / "industries.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    load_taxonomy.cache_clear()


@lru_cache
def load_business_profile() -> dict[str, Any]:
    with open(CONFIG_DIR / "business_profile.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def canonical_industry_name(name: str | None) -> str | None:
    if not name:
        return None
    low = name.strip().lower()
    if low in INDUSTRY_ALIASES:
        return INDUSTRY_ALIASES[low]
    for i in load_taxonomy()["industries"]:
        if i["name"].lower() == low or i["slug"].lower() == low:
            return i["name"]
    return None


def industry_names() -> list[str]:
    return [i["name"] for i in load_taxonomy()["industries"]]


def fallback_outcomes() -> list[str]:
    return list(load_taxonomy()["fallback_outcomes"])


def industry_by_name(name: str) -> dict | None:
    canon = canonical_industry_name(name) or name
    for i in load_taxonomy()["industries"]:
        if i["name"].lower() == (canon or "").lower():
            return i
    return None


def industry_by_slug(slug: str) -> dict | None:
    canon = canonical_industry_name(slug)
    for i in load_taxonomy()["industries"]:
        if i["slug"] == slug or i["name"].lower() == (slug or "").lower() or (canon and i["name"] == canon):
            return i
    return None


def sub_industries(industry: str) -> list[str]:
    i = industry_by_name(industry)
    return list(i["sub_industries"].keys()) if i else []


FREE_MAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.in", "yahoo.co.in", "ymail.com", "outlook.com", "hotmail.com",
    "live.com", "msn.com", "aol.com", "icloud.com", "me.com", "protonmail.com", "proton.me", "rediffmail.com",
    "zoho.com", "mail.com", "gmx.com", "yandex.com",
}


def domain_of(email: str | None) -> str:
    return email.rsplit("@", 1)[1].lower().strip() if email and "@" in email else ""


def is_free_mail(domain: str) -> bool:
    return domain.lower() in FREE_MAIL_DOMAINS
