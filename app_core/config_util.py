# app_core/config_util.py
from __future__ import annotations
import json, re
from pathlib import Path

_DEFAULT_CONFIG = {
    "rotasi": {
        "mode": "pair4",
        "order": ["P1J1","P2J1","P1J2","P2J2"],
        "increment_on_save": True
    },
    "hakim": {
        "exclude_jabatan_regex": r"\b(ketua|wakil)\b",
        "dropdown_show_cuti_default": False
    },
    "tampilan": {
        "tanggal_locale": "id-ID",
        "tanggal_long": True
    }
}

def validate_cfg(cfg: dict) -> dict:
    out = {**_DEFAULT_CONFIG, **(cfg or {})}
    # rotasi
    if out["rotasi"].get("mode") not in {"pair4","roundrobin"}:
        out["rotasi"]["mode"] = "pair4"
    keys = {"P1J1","P2J1","P1J2","P2J2"}
    order = out["rotasi"].get("order", [])
    if not isinstance(order, list) or not order or set(order) - keys:
        out["rotasi"]["order"] = ["P1J1","P2J1","P1J2","P2J2"]
    out["rotasi"]["increment_on_save"] = bool(out["rotasi"].get("increment_on_save", True))
    # hakim
    out["hakim"]["dropdown_show_cuti_default"] = bool(out["hakim"].get("dropdown_show_cuti_default", False))
    try:
        re.compile(out["hakim"].get("exclude_jabatan_regex", r"\b(ketua|wakil)\b"))
    except re.error:
        out["hakim"]["exclude_jabatan_regex"] = r"\b(ketua|wakil)\b"
    # tampilan
    out["tampilan"]["tanggal_locale"] = out["tampilan"].get("tanggal_locale", "id-ID")
    out["tampilan"]["tanggal_long"] = bool(out["tampilan"].get("tanggal_long", True))
    return out

def load_config(path: Path) -> dict:
    try:
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            return validate_cfg(raw)
    except Exception:
        pass
    return json.loads(json.dumps(_DEFAULT_CONFIG))

def save_config(cfg: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(validate_cfg(cfg), ensure_ascii=False, indent=2), encoding="utf-8")
