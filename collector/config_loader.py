"""Load collector config."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else ROOT / "config.yaml"
    with cfg_path.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    def resolve(p: str) -> Path:
        pp = Path(p)
        return pp if pp.is_absolute() else (ROOT / pp).resolve()

    cfg["db_path"] = str(resolve(cfg["db_path"]))
    cfg["export_dir"] = str(resolve(cfg["export_dir"]))
    return cfg


def all_etf_codes(cfg: dict[str, Any]) -> set[str]:
    codes: set[str] = set()
    for g in cfg["groups"]:
        for e in g["etfs"]:
            codes.add(str(e["code"]))
    return codes


def etf_codes_by_exchange(cfg: dict[str, Any], exchange: str) -> set[str]:
    codes: set[str] = set()
    for g in cfg["groups"]:
        for e in g["etfs"]:
            ex = str(e.get("exchange") or "sse").lower()
            if ex == exchange.lower():
                codes.add(str(e["code"]))
    return codes


def all_index_codes(cfg: dict[str, Any]) -> set[str]:
    return {str(g["index_code"]) for g in cfg["groups"]}


def groups_public(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Config slice for frontend meta.json."""
    out = []
    for g in cfg["groups"]:
        out.append(
            {
                "id": g["id"],
                "name": g["name"],
                "index_code": str(g["index_code"]),
                "index_name": g["index_name"],
                "etfs": [
                    {
                        "code": str(e["code"]),
                        "name": e["name"],
                        "exchange": str(e.get("exchange") or "sse"),
                    }
                    for e in g["etfs"]
                ],
            }
        )
    return out
