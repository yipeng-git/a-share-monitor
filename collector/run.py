"""CLI: backfill / daily / export."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date, datetime, timedelta

from config_loader import (
    all_index_codes,
    etf_codes_by_exchange,
    load_config,
)
from db import connect, upsert_index, upsert_shares
from export_json import export_all
from fetch_index import fetch_index_klines
from fetch_shares import fetch_sse_shares, filter_watched, to_iso_date
from fetch_szse import fetch_szse_scale_range, filter_watched_szse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _parse_ymd(s: str) -> date:
    s = s.replace("-", "")
    return datetime.strptime(s, "%Y%m%d").date()


def _iter_dates(start: date, end: date):
    cur = start
    while cur <= end:
        if cur.weekday() < 5:  # Mon-Fri; SSE returns empty on holidays
            yield cur
        cur += timedelta(days=1)


def _backfill_sse(cfg: dict, start_d: date, end_d: date, conn) -> None:
    codes = etf_codes_by_exchange(cfg, "sse")
    if not codes:
        return
    ok_days = 0
    empty_days = 0
    for d in _iter_dates(start_d, end_d):
        iso = d.isoformat()
        rows = fetch_sse_shares(iso)
        watched = filter_watched(rows, codes, iso)
        if not watched:
            empty_days += 1
            time.sleep(0.12)
            continue
        upsert_shares(conn, watched)
        ok_days += 1
        if ok_days % 20 == 0:
            logger.info("SSE shares progress: %s (%d days with data)", iso, ok_days)
        time.sleep(0.12)
    logger.info("SSE share backfill done: %d days ok, %d empty/holiday", ok_days, empty_days)


def _backfill_szse(cfg: dict, start_d: date, end_d: date, conn) -> None:
    codes = etf_codes_by_exchange(cfg, "szse")
    if not codes:
        logger.info("no SZSE ETFs configured, skip")
        return
    try:
        raw = fetch_szse_scale_range(
            start_d.strftime("%Y%m%d"),
            end_d.strftime("%Y%m%d"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("SZSE backfill failed: %s", exc)
        return
    watched = filter_watched_szse(raw, codes)
    if watched:
        upsert_shares(conn, watched)
        logger.info("SZSE upserted %d share rows (%d codes)", len(watched), len(codes))
    else:
        logger.warning("SZSE backfill: no watched rows in range")


def _refresh_indexes(cfg: dict, start_d: date, end_d: date, conn) -> None:
    prefix = cfg.get("eastmoney_secid_prefix", "1.")
    beg = start_d.strftime("%Y%m%d")
    end_s = end_d.strftime("%Y%m%d")
    for code in sorted(all_index_codes(cfg)):
        try:
            bars = fetch_index_klines(code, start=beg, end=end_s, secid_prefix=prefix)
            if bars:
                upsert_index(conn, bars)
        except Exception as exc:  # noqa: BLE001
            logger.error("index fetch failed for %s: %s", code, exc)
        time.sleep(0.3)


def cmd_backfill(cfg: dict, start: str | None, end: str | None) -> None:
    years = int(cfg.get("backfill_years", 2))
    end_d = _parse_ymd(end) if end else date.today()
    start_d = _parse_ymd(start) if start else end_d - timedelta(days=365 * years)

    conn = connect(cfg["db_path"])
    _backfill_sse(cfg, start_d, end_d, conn)
    _backfill_szse(cfg, start_d, end_d, conn)
    _refresh_indexes(cfg, start_d, end_d, conn)
    conn.close()
    export_all(cfg)


def cmd_daily(cfg: dict, trade_date: str | None) -> None:
    """Fetch one day SSE shares + recent SZSE window + refresh indexes."""
    if trade_date:
        iso = to_iso_date(trade_date)
        d = _parse_ymd(trade_date)
    else:
        d = date.today() - timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        iso = d.isoformat()

    conn = connect(cfg["db_path"])

    sse_codes = etf_codes_by_exchange(cfg, "sse")
    if sse_codes:
        rows = fetch_sse_shares(iso)
        watched = filter_watched(rows, sse_codes, iso)
        if not watched:
            logger.warning("no watched SSE ETF shares for %s", iso)
        else:
            upsert_shares(conn, watched)
            logger.info("SSE upserted %d share rows for %s", len(watched), iso)

    # SZSE: pull a short recent window (covers T+1 lag / holidays)
    szse_codes = etf_codes_by_exchange(cfg, "szse")
    if szse_codes:
        sz_start = d - timedelta(days=14)
        try:
            raw = fetch_szse_scale_range(
                sz_start.strftime("%Y%m%d"),
                d.strftime("%Y%m%d"),
            )
            watched = filter_watched_szse(raw, szse_codes)
            if watched:
                upsert_shares(conn, watched)
                logger.info("SZSE upserted %d share rows", len(watched))
            else:
                logger.warning("SZSE: no watched rows near %s", iso)
        except Exception as exc:  # noqa: BLE001
            logger.error("SZSE daily failed: %s", exc)

    beg = date.today() - timedelta(days=40)
    _refresh_indexes(cfg, beg, date.today(), conn)
    conn.close()
    export_all(cfg)


def cmd_export(cfg: dict) -> None:
    export_all(cfg)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="HJ ETF share collector")
    parser.add_argument("--config", default=None, help="path to config.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_bf = sub.add_parser("backfill", help="historical shares + indexes")
    p_bf.add_argument("--start", default=None, help="YYYYMMDD or YYYY-MM-DD")
    p_bf.add_argument("--end", default=None, help="YYYYMMDD or YYYY-MM-DD")

    p_d = sub.add_parser("daily", help="incremental daily update")
    p_d.add_argument("--date", default=None, help="share STAT_DATE YYYYMMDD")

    sub.add_parser("export", help="export SQLite → docs/data JSON")

    args = parser.parse_args(argv)
    cfg = load_config(args.config)

    if args.cmd == "backfill":
        cmd_backfill(cfg, args.start, args.end)
    elif args.cmd == "daily":
        cmd_daily(cfg, args.date)
    elif args.cmd == "export":
        cmd_export(cfg)
    else:
        parser.error(f"unknown cmd {args.cmd}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
