# app.py
import streamlit as st
from pathlib import Path

st.set_page_config(page_title="SAEF Sidang", layout="wide")

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
6. Klik **💾 Simpan ke Rekap (CSV)** → baris ditulis ke `data/rekap.csv`, dan **rotasi PP/JS** maju sesuai pengaturan.

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
- **JANGAN OTAK-ATIK TAB INI!!!!!

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
