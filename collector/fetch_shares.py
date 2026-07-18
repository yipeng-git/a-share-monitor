"""Fetch SSE ETF daily shares via query.sse.com.cn."""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Any

import requests

logger = logging.getLogger(__name__)

SSE_URL = "https://query.sse.com.cn/commonQuery.do"
HEADERS = {
    "Referer": "https://www.sse.com.cn/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
}


def _params(stat_date: str) -> dict[str, str]:
    # stat_date: YYYY-MM-DD
    return {
        "isPagination": "true",
        "pageHelp.pageSize": "10000",
        "pageHelp.pageNo": "1",
        "pageHelp.beginPage": "1",
        "pageHelp.cacheSize": "1",
        "pageHelp.endPage": "1",
        "sqlId": "COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L",
        "STAT_DATE": stat_date,
    }


def _parse_payload(data: dict[str, Any]) -> list[dict[str, Any]]:
    result = data.get("result")
    if isinstance(result, list) and result:
        return result
    page = data.get("pageHelp") or {}
    rows = page.get("data")
    if isinstance(rows, list):
        return rows
    return []


def _fetch_requests(stat_date: str, timeout: int = 30) -> list[dict[str, Any]]:
    r = requests.get(SSE_URL, params=_params(stat_date), headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return _parse_payload(r.json())


def _fetch_curl(stat_date: str, timeout: int = 30) -> list[dict[str, Any]]:
    qs = "&".join(f"{k}={v}" for k, v in _params(stat_date).items())
    url = f"{SSE_URL}?{qs}"
    cmd = [
        "curl",
        "-sS",
        "-m",
        str(timeout),
        "-H",
        f"Referer: {HEADERS['Referer']}",
        "-H",
        f"User-Agent: {HEADERS['User-Agent']}",
        url,
    ]
    out = subprocess.check_output(cmd, text=True)
    return _parse_payload(json.loads(out))


def fetch_sse_shares(stat_date: str) -> list[dict[str, Any]]:
    """
    Return raw SSE rows for STAT_DATE (YYYY-MM-DD).
    TOT_VOL is in 万份 (as published by SSE).
    """
    try:
        rows = _fetch_requests(stat_date)
        if rows:
            return rows
        logger.warning("SSE requests returned empty for %s, trying curl", stat_date)
    except Exception as exc:  # noqa: BLE001
        logger.warning("SSE requests failed for %s: %s; trying curl", stat_date, exc)

    rows = _fetch_curl(stat_date)
    if not rows:
        logger.warning("SSE curl also empty for %s", stat_date)
    return rows


def filter_watched(
    rows: list[dict[str, Any]],
    codes: set[str],
    trade_date: str,
) -> list[tuple[str, str, float, str | None]]:
    """-> (code, trade_date YYYY-MM-DD, total_share 万份, name)."""
    out: list[tuple[str, str, float, str | None]] = []
    for row in rows:
        code = str(row.get("SEC_CODE") or "").strip()
        if code not in codes:
            continue
        vol = row.get("TOT_VOL")
        if vol is None or vol == "":
            continue
        try:
            share = float(vol)
        except (TypeError, ValueError):
            continue
        name = row.get("SEC_NAME")
        out.append((code, trade_date, share, str(name) if name else None))
    return out


def to_iso_date(yyyymmdd: str) -> str:
    s = yyyymmdd.replace("-", "")
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
