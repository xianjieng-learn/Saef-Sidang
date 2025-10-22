# user_store.py
from __future__ import annotations
import json, os, tempfile
from pathlib import Path
from typing import Dict, Optional, Tuple

DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
USERS_JSON = DATA_DIR / "users.json"

# Struktur file:
# {
#   "users": {
#     "alice": {"salt_hex": "...", "hash_hex": "...", "role": "user"},
#     "admin": {"salt_hex": "...", "hash_hex": "...", "role": "admin"}
#   }
# }

USERS: Dict[str, Dict[str, str]] = {
    "nas": {
        "salt_hex": "d725e6ff1c6f38892fefdd24870128cc",
        "hash_hex": "1c21427302175ce3f728c4aca272e792f7bdead05d9f9fc4f67002668e1b9371",
        "role": "admin",
    },
    "admin": {
        "salt_hex": "ed78cd582b87d20ba5fb35017e33d29d",
        "hash_hex": "5f4fda1b36d0b39e0c1a63d6cda21d1086ce42b7ae9952bc08abcb9876064de7",
        "role": "admin",
    },
    "ptsp": {
        "salt_hex": "49cad1db41ef335569837d42ce42a6df",
        "hash_hex": "3646b5eb1e6c56e4e02578357be841e1cb280dc0d2e4f939debabc778c5acc9c",
        "role": "user",
    },
    "saef": {
        "salt_hex": "5afc223f2240a034c91e8f83ed25bfad",
        "hash_hex": "2de79f69c249b0fdde6360e621fb8224c773d25be79cfa4eb78eba5f8b29a886",
        "role": "admin",
    }
}
def _empty() -> Dict[str, Dict[str, str]]:
    return {"users": {}}

def load_users() -> Dict[str, Dict[str, str]]:
    if not USERS_JSON.exists():
        return _empty()
    try:
        data = json.loads(USERS_JSON.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "users" not in data or not isinstance(data["users"], dict):
            return _empty()
        return data
    except Exception:
        return _empty()

def save_users(data: Dict[str, Dict[str, str]]) -> None:
    """Tulis JSON secara atomik (write-to-temp lalu rename)."""
    USERS_JSON.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(prefix="users.json.", dir=str(USERS_JSON.parent))
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, USERS_JSON)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

def get_user(username: str) -> Optional[Dict[str, str]]:
    data = load_users()
    return (data["users"].get(username) if data else None)

def list_users() -> Dict[str, Dict[str, str]]:
    return load_users()["users"]

def upsert_user(username: str, salt_hex: str, hash_hex: str, role: str = "user") -> None:
    data = load_users()
    data["users"][username] = {"salt_hex": salt_hex, "hash_hex": hash_hex, "role": role}
    save_users(data)

def delete_user(username: str) -> Tuple[bool, str]:
    """Hapus user; cegah hapus admin terakhir."""
    data = load_users()
    users = data["users"]
    if username not in users:
        return False, "User tidak ditemukan."

    # Cegah hapus admin terakhir
    admins = [u for u, r in users.items() if r.get("role") == "admin"]
    if users[username].get("role") == "admin" and len(admins) <= 1:
        return False, "Tidak boleh menghapus admin terakhir."

    users.pop(username, None)
    save_users(data)
    return True, f"User '{username}' dihapus."
