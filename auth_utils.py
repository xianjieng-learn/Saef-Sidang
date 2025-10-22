# auth_utils.py
from __future__ import annotations
import os, hmac, hashlib, binascii
from dataclasses import dataclass
from typing import Dict, Optional

# Contoh user store (sebaiknya ambil dari env / file terpisah)
# Format: username -> {salt_hex, hash_hex, role}
USERS: Dict[str, Dict[str,str]] = {
    # username: nas, password: 12345  (contoh — ganti punyamu!)
    "nas": {
        "salt_hex": "8e7f6b7a0e6f4a8d9c1b2a3c4d5e6f70",
        "hash_hex": "c9c8f2b4853f7f5d3d2bc5e6f9a1c0b34a1b2c3d4e5f6789ab01cd23ef45a678",
        "role": "admin",
    },
    # username lain...
}

PBKDF2_ITER = 120_000

def pbkdf2_hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITER, dklen=32)

def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    salt = binascii.unhexlify(salt_hex)
    expect = binascii.unhexlify(hash_hex)
    got = pbkdf2_hash(password, salt)
    return hmac.compare_digest(got, expect)

def hash_new_password(password: str) -> tuple[str,str]:
    """Utility sekali jalan untuk bikin pasangan (salt_hex, hash_hex)."""
    salt = os.urandom(16)
    h = pbkdf2_hash(password, salt)
    return binascii.hexlify(salt).decode(), binascii.hexlify(h).decode()

def get_user(username: str) -> Optional[Dict[str,str]]:
    return USERS.get(username)
