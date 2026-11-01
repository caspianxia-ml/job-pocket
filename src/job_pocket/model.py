from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

from .config import allowed_url


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def job_identity(href: str, base: str = "https://www.zhipin.com/") -> tuple[str, str] | None:
    url = urljoin(base, href)
    if not allowed_url(url):
        return None
    match = re.fullmatch(r"/job_detail/([A-Za-z0-9_-]+)\.html", urlsplit(url).path)
    if not match:
        return None
    ident = match.group(1)
    return ident, f"https://www.zhipin.com/job_detail/{ident}.html"


def card_record(raw: dict, source: str) -> dict | None:
    ident = job_identity(raw.get("href", ""), source)
    if not ident or not raw.get("title", "").strip():
        return None
    requirements = raw.get("requirements", [])
    record = {key: raw.get(key, "") for key in (
        "title", "salary", "location", "company", "benefits", "card_text"
    )}
    record.update({
        "job_id": ident[0], "url": ident[1], "source_url": source,
        "requirements": " | ".join(requirements),
        "skills": " | ".join(raw.get("skills", [])),
        "company_info": " | ".join(raw.get("company_info", [])),
        "experience": next((x for x in requirements if re.search(r"经验|\d+.*年|应届|在校", x)), ""),
        "education": next((x for x in requirements if re.search(r"学历|本科|硕士|博士|大专|中专|高中|初中", x)), ""),
        "jd": "", "address": "", "detail_title": "", "jd_status": "pending",
        "jd_note": "", "captured_at": now(), "updated_at": now(),
    })
    return record
