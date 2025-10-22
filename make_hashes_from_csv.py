# make_hashes_from_csv.py
import csv
from auth_utils import hash_new_password

with open("reset_passwords.csv", newline="", encoding="utf-8") as f, \
     open("users_hashed_out.csv", "w", newline="", encoding="utf-8") as g:
    r = csv.DictReader(f)
    w = csv.writer(g)
    w.writerow(["username","role","salt_hex","hash_hex"])
    for row in r:
        user = row["username"].strip()
        pwd  = row["new_password"]
        role = (row.get("role") or "user").strip()
        salt_hex, hash_hex = hash_new_password(pwd)
        w.writerow([user, role, salt_hex, hash_hex])

print("OK -> users_hashed_out.csv dibuat. Tempel isinya ke USERS di auth_utils.py")
