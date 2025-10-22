# ==== cooldown v2 (token-based) ====
from datetime import date
import json
from pathlib import Path

_COOL_V2_PATH = Path("data/cooldown_v2.json")

def _cool_v2_load():
    if _COOL_V2_PATH.exists():
        try:
            return json.loads(_COOL_V2_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    # default store
    return {"epoch": 1, "map": {}, "auto_daily": False, "last_reset_date": None}

def _cool_v2_save(store):
    _COOL_V2_PATH.parent.mkdir(parents=True, exist_ok=True)
    _COOL_V2_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")

def _cool_v2_is_active(hakim: str) -> bool:
    """Aktif jika hakim ditandai di epoch yang sedang berjalan."""
    s = _cool_v2_load()
    return s["map"].get(hakim) == s["epoch"]

def _cool_v2_mark(hakim: str):
    """Tandai hakim ini cooldown pada epoch saat ini."""
    s = _cool_v2_load()
    s["map"][hakim] = s["epoch"]
    _cool_v2_save(s)

def _cool_v2_reset_all():
    """Reset global: naikkan epoch → semua tanda otomatis non-aktif."""
    s = _cool_v2_load()
    s["epoch"] = int(s.get("epoch", 1)) + 1
    # opsional: kosongkan map untuk merapikan file (tidak wajib)
    s["map"] = {}
    s["last_reset_date"] = date.today().isoformat()
    _cool_v2_save(s)

def _cool_v2_toggle_auto_daily(enabled: bool):
    s = _cool_v2_load()
    s["auto_daily"] = bool(enabled)
    _cool_v2_save(s)

def _cool_v2_maybe_auto_reset_today():
    """Jika auto_daily ON dan last_reset_date != hari ini → reset otomatis."""
    s = _cool_v2_load()
    if s.get("auto_daily"):
        today = date.today().isoformat()
        if s.get("last_reset_date") != today:
            s["epoch"] = int(s.get("epoch", 1)) + 1
            s["map"] = {}
            s["last_reset_date"] = today
            _cool_v2_save(s)
