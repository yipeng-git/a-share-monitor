"""Fetch SZSE ETF daily shares via official ShowReport API.

SZSE publishes fund scale daily data (xlsx) with a max ~6 month window per request.
Shares are reported in 份; we store 万份 to align with SSE.
"""

from __future__ import annotations

import io
import logging
import random
import warnings
from datetime import date, datetime, timedelta
from typing import Any

import requests

logger = logging.getLogger(__name__)

URL = "https://www.szse.cn/api/report/ShowReport"
HEADERS = {
    "Host": "www.szse.cn",
    "Referer": "https://www.szse.cn/market/fund/volume/etf/index.html",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
    ),
}


def _ymd(d: date) -> str:
    return d.strftime("%Y%m%d")


def _iso(d: date) -> str:
    return d.isoformat()


def _chunk_ranges(start: date, end: date, max_days: int = 180):
    """Yield (chunk_start, chunk_end) inclusive, each <= max_days span."""
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=max_days - 1), end)
        yield cur, chunk_end
        cur = chunk_end + timedelta(days=1)


def fetch_szse_scale_range(
    start: str,
    end: str,
) -> list[dict[str, Any]]:
    """
    Fetch SZSE ETF scale rows for [start, end] (YYYYMMDD or YYYY-MM-DD).
    Returns list of {code, trade_date, share_wan, name}.
    """
    start_d = datetime.strptime(start.replace("-", ""), "%Y%m%d").date()
    end_d = datetime.strptime(end.replace("-", ""), "%Y%m%d").date()
    if start_d > end_d:
        return []

    out: list[dict[str, Any]] = []
    for cs, ce in _chunk_ranges(start_d, end_d, max_days=180):
        rows = _fetch_one_window(cs, ce)
        out.extend(rows)
    return out


def _fetch_one_window(start: date, end: date) -> list[dict[str, Any]]:
    params = {
        "SHOWTYPE": "xlsx",
        "CATALOGID": "scsj_fund_jjgm",
        "TABKEY": "tab1",
        "txtStart": _iso(start),
        "txtEnd": _iso(end),
        "jjlb": "ETF",
        "random": str(random.random()),
    }
    r = requests.get(URL, params=params, headers=HEADERS, timeout=60)
    r.raise_for_status()

    try:
        import openpyxl  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("openpyxl required for SZSE xlsx parse") from exc

    import pandas as pd

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        df = pd.read_excel(io.BytesIO(r.content), engine="openpyxl")

    df = df.dropna(how="all")
    if df.empty:
        logger.warning("SZSE empty window %s ~ %s", start, end)
        return []

    rename = {}
    if "基金规模(份)" in df.columns:
        rename["基金规模(份)"] = "share_fen"
    elif "基金份额" in df.columns:
        rename["基金份额"] = "share_fen"
    df = df.rename(columns=rename)

    if "基金代码" not in df.columns or "share_fen" not in df.columns:
        logger.warning("SZSE unexpected columns: %s", list(df.columns))
        return []

    code_num = pd.to_numeric(df["基金代码"], errors="coerce")
    df = df[code_num.notna()].copy()
    df["code"] = code_num[code_num.notna()].astype(int).astype(str).str.zfill(6)

    if "日期" in df.columns:
        df["trade_date"] = pd.to_datetime(df["日期"], errors="coerce").dt.strftime("%Y-%m-%d")
    else:
        logger.warning("SZSE missing 日期 column")
        return []

    df["share_fen"] = (
        df["share_fen"].astype(str).str.replace(",", "", regex=False)
    )
    df["share_fen"] = pd.to_numeric(df["share_fen"], errors="coerce")
    df = df[df["share_fen"].notna() & df["trade_date"].notna()]

    name_col = "基金简称" if "基金简称" in df.columns else None
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        share_wan = float(row["share_fen"]) / 10000.0
        name = None
        if name_col is not None:
            raw_name = row[name_col]
            if raw_name is not None and str(raw_name) not in ("", "nan", "None"):
                name = str(raw_name)
        rows.append(
            {
                "code": row["code"],
                "trade_date": row["trade_date"],
                "share_wan": share_wan,
                "name": name,
            }
        )

    logger.info("SZSE window %s~%s: %d rows", start, end, len(rows))
    return rows


def filter_watched_szse(
    rows: list[dict[str, Any]],
    codes: set[str],
) -> list[tuple[str, str, float, str | None]]:
    """-> (code, trade_date, total_share_wan, name)."""
    out: list[tuple[str, str, float, str | None]] = []
    for row in rows:
        code = row["code"]
        if code not in codes:
            continue
        out.append((code, row["trade_date"], row["share_wan"], row.get("name")))
    return out
