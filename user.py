# make_user.py
from auth_utils import hash_new_password

USERNAME = "admin"          # ganti
PLAINTEXT = "pajt2025"  # ganti

salt_hex, hash_hex = hash_new_password(PLAINTEXT)
print("=== Tempel ke auth_utils.py → USERS ===")
print(f'''"{USERNAME}": {{
    "salt_hex": "{salt_hex}",
    "hash_hex": "{hash_hex}",
    "role": "admin",  # atau "user"
}},''')
