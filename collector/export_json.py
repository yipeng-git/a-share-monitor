"""Export SQLite → compact JSON for GitHub Pages."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from config_loader import groups_public
from db import connect

logger = logging.getLogger(__name__)
TZ = ZoneInfo("Asia/Shanghai")


def export_all(cfg: dict[str, Any]) -> Path:
    export_dir = Path(cfg["export_dir"])
    export_dir.mkdir(parents=True, exist_ok=True)
    conn = connect(cfg["db_path"])

    share_rows = conn.execute(
        """
        SELECT trade_date, code, total_share
        FROM etf_daily_share
        ORDER BY trade_date, code
        """
    ).fetchall()
    shares = [[r["trade_date"], r["code"], round(r["total_share"], 4)] for r in share_rows]

    index_rows = conn.execute(
        """
        SELECT trade_date, code, open, high, low, close, volume
        FROM index_daily
        ORDER BY trade_date, code
        """
    ).fetchall()
    indexes = []
    for r in index_rows:
        indexes.append(
            [
                r["trade_date"],
                r["code"],
                r["open"],
                r["high"],
                r["low"],
                r["close"],
                r["volume"],
            ]
        )

    latest_share_date = conn.execute(
        "SELECT MAX(trade_date) AS d FROM etf_daily_share"
    ).fetchone()["d"]
    latest_index_date = conn.execute(
        "SELECT MAX(trade_date) AS d FROM index_daily"
    ).fetchone()["d"]

    meta = {
        "schema": {
            "etf_shares": ["trade_date", "code", "total_share_wan"],
            "indexes": [
                "trade_date",
                "code",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ],
            "note": (
                "total_share_wan = ETF 总份额（万份），非汇金精确持仓；"
                "含上交所(可回溯)与深交所(官方日频窗口约6个月/次)"
            ),
        },
        "groups": groups_public(cfg),
        "share_data_date": latest_share_date,
        "index_data_date": latest_index_date,
        "szse_note": (
            "深交所份额来自官网基金规模日频接口；单次查询窗口约6个月，"
            "可分段回填。未发现可直接下载的完整多年开源历史库。"
        ),
        "updated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "updated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "counts": {"shares": len(shares), "indexes": len(indexes)},
    }

    _write(export_dir / "meta.json", meta)
    _write(export_dir / "etf_shares.json", shares)
    _write(export_dir / "indexes.json", indexes)

    # Yearly shards for healthier git (shares)
    by_year: dict[str, list] = {}
    for row in shares:
        year = row[0][:4]
        by_year.setdefault(year, []).append(row)
    shares_dir = export_dir / "shares"
    shares_dir.mkdir(exist_ok=True)
    for year, rows in by_year.items():
        _write(shares_dir / f"{year}.json", rows)

    logger.info(
        "exported %d shares, %d index bars → %s",
        len(shares),
        len(indexes),
        export_dir,
    )
    conn.close()
    return export_dir


def _write(path: Path, obj: Any) -> None:
    path.write_text(
        json.dumps(obj, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
