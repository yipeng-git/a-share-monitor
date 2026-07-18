"""Fetch A-share index daily bars via Sina Finance."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

URL = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.sina.com.cn/",
}


def fetch_index_klines(
    index_code: str,
    start: str = "20200101",
    end: str = "20500101",
    secid_prefix: str = "1.",  # unused; kept for call-site compat
    retries: int = 4,
    datalen: int = 1023,
) -> list[tuple[str, str, float, float, float, float, float | None]]:
    """
    Return rows: (code, trade_date, open, high, low, close, volume).
    Sina returns up to `datalen` most-recent daily bars; then filter by start/end.
    """
    del secid_prefix  # API uses sh/sz symbol instead
    # 上证指数 000xxx → sh；深证系列 399xxx → sz
    prefix = "sz" if str(index_code).startswith("399") else "sh"
    symbol = f"{prefix}{index_code}"
    params = {
        "symbol": symbol,
        "scale": "240",
        "ma": "no",
        "datalen": str(datalen),
    }

    last_err: Exception | None = None
    raw: list[dict[str, Any]] = []
    for attempt in range(retries):
        try:
            r = requests.get(URL, params=params, headers=HEADERS, timeout=60)
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, list):
                raise ValueError(f"unexpected payload type: {type(data)}")
            raw = data
            break
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            wait = 1.5 * (attempt + 1)
            logger.warning(
                "index %s fetch attempt %d failed: %s; retry in %.1fs",
                index_code,
                attempt + 1,
                exc,
                wait,
            )
            time.sleep(wait)
    else:
        raise RuntimeError(f"index {index_code} fetch failed") from last_err

    start_iso = _to_iso(start)
    end_iso = _to_iso(end)
    rows: list[tuple[str, str, float, float, float, float, float | None]] = []
    for item in raw:
        trade_date = str(item.get("day") or "")
        if not trade_date:
            continue
        if trade_date < start_iso or trade_date > end_iso:
            continue
        try:
            open_ = float(item["open"])
            high = float(item["high"])
            low = float(item["low"])
            close = float(item["close"])
            vol_raw = item.get("volume")
            volume = float(vol_raw) if vol_raw not in (None, "", "-") else None
        except (KeyError, TypeError, ValueError):
            continue
        rows.append((index_code, trade_date, open_, high, low, close, volume))

    rows.sort(key=lambda x: x[1])
    logger.info("index %s: %d bars", index_code, len(rows))
    return rows


def _to_iso(ymd: str) -> str:
    s = ymd.replace("-", "")
    if len(s) == 8:
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return ymd
