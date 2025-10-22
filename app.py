# app.py
from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
import streamlit as st
from app_core.login import _ensure_auth 
# === import dari auth_utils.py buatanmu ===
# pastikan di folder yang sama dengan app.py
from auth_utils import get_user, verify_password  # get_user(username) -> dict | None

# ================== CONFIG APP ==================
st.set_page_config(page_title="SAEF Sidang", layout="wide")
SESSION_TTL_HOURS = 1  # sesi kedaluwarsa otomatis

# ================== AUTH HELPERS ==================
def _set_authed(username: str, role: str = "user"):
    st.session_state["auth_user"] = username
    st.session_state["auth_role"] = role or "user"
    st.session_state["auth_exp"]  = datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)

def _clear_auth():
    for k in ("auth_user", "auth_role", "auth_exp"):
        st.session_state.pop(k, None)

def _is_authed() -> bool:
    u = st.session_state.get("auth_user")
    exp = st.session_state.get("auth_exp")
    if not u or not exp:
        return False
    if datetime.utcnow() > exp:
        _clear_auth()
        return False
    # refresh idle timeout setiap interaksi
    st.session_state["auth_exp"] = datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)
    return True

def _login_view():
    st.markdown("## 🔐 Masuk ke SAEF Sidang")
    st.caption("Silakan login terlebih dahulu.")

    with st.form("saef_login_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            username = st.text_input("Username", autocomplete="username")
        with c2:
            password = st.text_input("Password", type="password", autocomplete="current-password")

        colb = st.columns([1,1,2])
        with colb[0]:
            submitted = st.form_submit_button("Masuk", use_container_width=True)
        with colb[1]:
            reset_btn = st.form_submit_button("Reset", use_container_width=True)

        if submitted:
            user = (username or "").strip()
            rec = get_user(user)  # dari auth_utils.py (berisi salt_hex, hash_hex, role, dst.)
            if not rec:
                st.error("Username tidak ditemukan.")
                return
            if not verify_password(password or "", rec["salt_hex"], rec["hash_hex"]):
                st.error("Password salah.")
                return
            # sukses
            _set_authed(user, rec.get("role", "user"))
            st.success(f"Selamat datang, {user}!")
            st.rerun()
        elif reset_btn:
            st.rerun()

def _topbar_with_router():
    l, m, r = st.columns([5,3,1])
    with l:
        st.caption(
            f"👤 Masuk sebagai **{st.session_state.get('auth_user','?')}** "
            f"(role: {st.session_state.get('auth_role','user')})"
        )
    with r:
        if st.button("Logout", use_container_width=True):
            _clear_auth()
            st.rerun()

    # Router cepat (opsional selain sidebar Pages bawaan Streamlit)
    with st.expander("🔗 Quick Links (Pages)", expanded=False):
        # ganti sesuai isi folder pages/ milikmu
        st.page_link("pages/1_Input_&_Hasil.py",   label="📥 Input & Hasil", icon="📥")
        st.page_link("pages/2_Rekap.py",           label="📊 Rekap",          icon="📊")
        st.page_link("pages/3_Data_Hakim.py",      label="⚖️ Data Hakim",     icon="⚖️")
        st.page_link("pages/3_Data_PP.py",         label="🧑‍💼 Data PP",       icon="🧑‍💼")
        st.page_link("pages/3_Data_JS.py",         label="📨 Data JS",        icon="📨")
        st.page_link("pages/3_Data_Libur.py",      label="🏖️ Data Libur",     icon="🏖️")
        st.page_link("pages/3_Data_SK_Majelis.py", label="📑 Data SK Majelis", icon="📑")
        st.page_link("pages/4_BATCH_INSTRUMEN.py", label="🧰 Batch Instrumen", icon="🧰")

# ================== LOGIN GATE ==================
if not _is_authed():
    _login_view()
    st.stop()

# ================== APP CONTENT (ASLI KAMU) ==================
_topbar_with_router()

# === Setup folder data (CSV-only) ===
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# === Header ===
st.title("SAEF Sidang — Master Data, Rekap & Penjadwalan (LIAT TUTORIAL)")
st.caption("Semua data disimpan sebagai CSV/JSON di folder `data/`.")

# === Tabs: Overview & Tutorial ===
tab_overview, tab_tutorial = st.tabs(["🏠 Home", "📖 Tutorial"])

with tab_overview:
    st.markdown("""
Gunakan menu **Pages** (kiri) untuk:

Lihat cara pakai di menu Tutorial
                        
**Master (CSV)**
- Hakim, PP, JS, JS Ghoib, Libur, SK Majelis

**Input & Rekap**
- 📥 Input & Hasil — tambah perkara, auto-assign Ketua/PP/JS, hitung tanggal sidang
- 📊 Rekap — lihat & **edit per baris** (dropdown Ketua sama seperti di Tab Input)

**Batch / Cetak**
- 🧰 Batch Instrument (PDF) — Group by JS/PP/Hakim, dengan footer timestamp & penomoran per grup

> Catatan: Rotasi PP/JS & preferensi berada di **⚙️ Pengaturan** (disimpan di `data/config.json`).
    """)

    # Status file di folder data/
    files = [
        "hakim_df.csv", "pp_df.csv", "js_df.csv", "js_ghoib.csv",
        "libur.csv", "sk_df.csv", "rekap.csv", "config.json", "rrpair_token.json"
    ]
    existing = [f for f in files if (DATA_DIR / f).exists()]
    missing  = [f for f in files if not (DATA_DIR / f).exists()]

    with st.expander("📁 Status Berkas di folder data/"):
        st.write("**Ada:**", ", ".join(existing) if existing else "—")
        st.write("**Belum ada:**", ", ".join(missing) if missing else "—")

with tab_tutorial:
    st.markdown("""
# Tutorial Penggunaan — “📥 Input & Hasil”

## 1) Struktur & Sumber Data
Aplikasi ini **hanya pakai CSV di folder `data/`**. File penting:
- `data/rekap.csv` — output utama rekap perkara  
- `data/hakim_df.csv`, `data/pp_df.csv`, `data/js_df.csv` — master ketua/PP/JS  
- `data/libur.csv` — daftar hari libur (kolom `tanggal`)  
- (Opsional) `data/sk_df.csv` / `sk_majelis.csv` — SK Majelis (kolom `ketua`, `anggota1`, `anggota2`, `pp1`, `pp2`, `js1`, `js2`, dll)

> Tips: Kolom `aktif` (1/TRUE/YA) membantu filter dropdown & rotasi. Nama kolom umum sudah dinormalisasi otomatis
(misal “anggota 1” → `anggota1`, “hari sidang”/“hari” → `hari_sidang`).

---

## 2) Tab 1 — 📝 Input
Untuk **mencatat perkara baru** dan menghasilkan penugasan otomatis.

Langkah:
1. Isi **Nomor Perkara**, **Tanggal Register**, **Klasifikasi**, **Jenis Perkara** (Biasa / ISTBAT / GHOIB / ROGATORI / MAFQUD), dan **Metode** (E-Court/Manual).  
2. **Ketua (opsional, override)**  
   - Jika dikosongkan, sistem memilih **ketua otomatis** berdasarkan beban rekap, hari sidang, libur, dan cuti.  
   - Toggle **“Tampilkan yang cuti (override)”** untuk tetap menampilkan nama yang sedang cuti.  
3. **Anggota 1/2** otomatis mengikuti baris SK ketua terpilih.  
4. **PP/JS** disarankan dari SK + rotasi.  
   - Untuk **Jenis = GHOIB**, kandidat **JS Ghoib** dipilih dari `data/js_ghoib.csv` (beban terendah).  
   - Kamu bisa **override** PP/JS dari dropdown bila perlu.  
5. **Tanggal Sidang** dihitung otomatis dari jenis + hari sidang ketua + libur.  
   - Bisa **override** (mode “Bebas” atau “Sesuaikan ke hari sidang + skip libur”).  
6. Klik **💾 Simpan ke Rekap (CSV)** → baris ditulis ke `rekap.csv`, dan **rotasi PP/JS** maju sesuai pengaturan.

---

## 3) Tab 2 — 📊 Rekap
Lihat **rekap per tanggal register** dan **edit/hapus** per baris.
- Pilih **Tanggal**, daftar perkara di tanggal tersebut akan tampil.  
- Klik **✏️** untuk **edit**:
  - **Ketua** memakai **dropdown yang sama** seperti di Tab 1 (memperhatikan aktif/cuti/hari sidang).  
  - **Anggota 1/2** otomatis dari SK ketua yang dipilih (non-editable).  
  - **PP/JS** ada saran & boleh override.  
  - **Tanggal Sidang** bisa diubah; centang **override** jika ingin menandai manual.  
- Klik **🗑️** untuk menghapus baris dari `rekap.csv`.

---

## 4) Tab 3 — 🫥 JS Ghoib (Debug)
Memantau & mengatur **beban JS Ghoib**. Berguna untuk menyeimbangkan penugasan ketika jenis perkara **GHOIB**.

---

## 5) Tab 4 — ⚙️ Pengaturan JANGAN DIOTAK-ATIK TAB INI!!!!!
- **JANGAN OTAK-ATIK TAB INI!!!!!**

---

## 6) Alur Rekomendasi (ringkas)
Ketua → ambil baris SK → auto **Anggota1/2** → saran **PP/JS** via rotasi (atau JS Ghoib) → hitung **Tanggal Sidang** (jenis + hari sidang + libur, dengan opsi override) → simpan ke `rekap.csv`.

---

## 7) Tips & Troubleshooting
- **Nama kolom beda-beda?** Aplikasi sudah menormalisasi kolom umum; pastikan kolom kunci ada.  
- **Dropdown ketua kosong?** Cek `hakim_df.csv` (kolom `nama`, `aktif`, dan `hari_sidang`/`hari`), juga `data/libur.csv` & data cuti.  
- **Tanggal override jatuh di libur (mode Bebas)?** Itu dibiarkan apa adanya. Pakai mode “Sesuaikan ke hari sidang + skip libur” agar otomatis digeser.  
- **Duplikat komponen Streamlit (error key/ID)?** Beri `key` yang **unik** pada elemen berulang (terutama tombol/input di dalam loop).

---

## 8) BATCH Instrumen
- **Print Instrumen menggunakan BATCH Instrumen**.                  
    """)
