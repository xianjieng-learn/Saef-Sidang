# pages/1_📥_Input_&_Hasil.py
# Ketua by beban(aktif), Anggota STRICT same SK row
# PP/JS dari SK, rotate HANYA saat Simpan (pair 4-step: P1J1→P2J1→P1J2→P2J2)
# Tgl sidang: "Biasa" = H+8..H+14, skip libur, ke hari sidang ketua berikutnya
from __future__ import annotations
import re
from datetime import date, datetime, timedelta
from pathlib import Path
import pandas as pd
import streamlit as st

from app_core.data_io import load_with_sk, save_table
from app_core.helpers import HARI_MAP, format_tanggal_id, compute_nomor_tipe

# ===== JS Ghoib (opsional) =====
try:
    from app_core.helpers_js_ghoib import choose_js_ghoib_db
except Exception:
    # Fallback GHOIB yang benar2 memilih JS aktif dengan beban GHOIB paling sedikit
    def choose_js_ghoib_db(rekap_df, use_aktif=True):
        # Ambil sumber kandidat: prefer js_ghoib_df, kalau kosong pakai js_df, kalau tetap kosong pakai daftar di rekap_df
        cand_df = js_ghoib_df if isinstance(js_ghoib_df, pd.DataFrame) and not js_ghoib_df.empty else js_df
        names = []

        if isinstance(cand_df, pd.DataFrame) and not cand_df.empty:
            tmp = cand_df.copy()
            # filter aktif kalau ada
            if use_aktif and "aktif" in tmp.columns:
                tmp = tmp[tmp["aktif"].apply(_is_active_value)]
            name_col = next((c for c in ["nama","js","Nama","NAMA"] if c in tmp.columns), None)
            if name_col:
                names = [str(x).strip() for x in tmp[name_col].tolist() if str(x).strip()]

        # fallback: pakai nama JS yang pernah muncul di rekap
        if not names and isinstance(rekap_df, pd.DataFrame) and "js" in rekap_df.columns:
            names = sorted({str(x).strip() for x in rekap_df["js"].tolist() if str(x).strip()})

        if not names:
            return ""  # tidak ada kandidat

        # Hitung beban GHOIB dari rekap (dinamis)
        dyn_counts = {}
        if isinstance(rekap_df, pd.DataFrame) and not rekap_df.empty:
            rd = rekap_df.copy()
            rd["jenis_perkara"] = rd.get("jenis_perkara", "").astype(str)
            rd["js"] = rd.get("js", "").astype(str)
            for n in names:
                dyn_counts[n] = int(
                    rd[(rd["jenis_perkara"].str.upper() == "GHOIB") & (rd["js"].str.strip() == n)].shape[0]
                )

        # Jika ada kolom 'Total Ghoib' di js_ghoib_df, jadikan pembobot sekunder
        base_counts = {}
        if isinstance(js_ghoib_df, pd.DataFrame) and not js_ghoib_df.empty:
            col_name = next((c for c in ["Total Ghoib","total_ghoib","total ghoib"] if c in js_ghoib_df.columns), None)
            name_col = next((c for c in ["nama","js","Nama","NAMA"] if c in js_ghoib_df.columns), None)
            if col_name and name_col:
                for _, r in js_ghoib_df.iterrows():
                    nm = str(r.get(name_col,"")).strip()
                    if nm:
                        try:
                            base_counts[nm] = int(r.get(col_name, 0))
                        except Exception:
                            base_counts[nm] = 0

        # Skor: (beban GHOIB dinamis sekarang, total ghoib historis jika ada, tie-break alfabet)
        def _score(nm: str):
            return (dyn_counts.get(nm, 0), base_counts.get(nm, 0), nm.lower())

        names_sorted = sorted(names, key=_score)
        return names_sorted[0] if names_sorted else ""

st.set_page_config(page_title="📥 Input & Hasil", page_icon="📥", layout="wide")
st.header("Input & Hasil")

# ===== Util teks/nama =====
_PREFIX_RX = re.compile(r"^\s*((drs?|dra|prof|ir|apt|h|hj|kh|ust|ustadz|ustadzah)\.?\s+)+", flags=re.IGNORECASE)
_SUFFIX_PATTERNS = [
    r"s\.?\s*h\.?", r"s\.?\s*h\.?\s*i\.?", r"m\.?\s*h\.?", r"m\.?\s*h\.?\s*i\.?",
    r"s\.?\s*ag", r"m\.?\s*ag", r"m\.?\s*kn", r"m\.?\s*hum",
    r"s\.?\s*kom", r"s\.?\s*psi", r"s\.?\s*e", r"m\.?\s*m", r"m\.?\s*a",
    r"llb", r"llm", r"phd", r"se", r"ssi", r"sh", r"mh"
]
_SUFFIX_RX = re.compile(r"(,?\s+(" + r"|".join(_SUFFIX_PATTERNS) + r"))+$", flags=re.IGNORECASE)

def _clean_text(s: str) -> str:
    x = str(s or "").replace("\u00A0", " ").strip()
    x = x.replace(" ,", ",").replace(" .", ".")
    x = re.sub(r"\s+", " ", x).strip()
    return x

def _name_key(s: str) -> str:
    if not isinstance(s, str): return ""
    x = _clean_text(s).replace(",", " ")
    x = _SUFFIX_RX.sub("", x)
    x = _PREFIX_RX.sub("", x)
    x = re.sub(r"[^\w\s]", " ", x)
    x = re.sub(r"\s+", " ", x).strip().lower()
    toks = [t for t in x.split() if t not in {"s","h","m","e"}]
    return " ".join(toks)

def _tokset(s: str) -> set[str]:
    return set([t for t in _name_key(s).split() if t])

def _is_active_value(v) -> bool:
    s = re.sub(r"[^A-Z0-9]+", "", str(v).strip().upper())
    if s in {"1","YA","Y","TRUE","T","AKTIF","ON"}: return True
    if s in {"0","TIDAK","TDK","NO","N","FALSE","F","NONAKTIF","OFF","NONE","NAN",""}: return False
    try: return float(s) != 0.0
    except Exception: return False

def _majelis_rank(s: str) -> int:
    m = re.search(r"(\d+)", str(s))
    return int(m.group(1)) if m else 10**9

def _standardize_cols(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty: return pd.DataFrame()
    ren = {}
    for c in list(df.columns):
        raw = str(c).replace("\ufeff","").strip()
        k = re.sub(r"\s+", " ", raw).strip().lower().replace("_"," ")
        if   k in {"majelis","nama majelis","majelis ruang sidang","majelis rs"}: new = "majelis"
        elif k in {"hari","hari sidang","hari sk"}: new = "hari"
        elif k in {"ketua","hakim ketua","ketua majelis"}: new = "ketua"
        elif k in {"anggota1","anggota 1","a1","anggota i"}: new = "anggota1"
        elif k in {"anggota2","anggota 2","a2","anggota ii"}: new = "anggota2"
        elif k in {"pp1","panitera pengganti 1","panitera 1"}: new = "pp1"
        elif k in {"pp2","panitera pengganti 2","panitera 2"}: new = "pp2"
        elif k in {"js1","jurusita 1"}: new = "js1"
        elif k in {"js2","jurusita 2"}: new = "js2"
        elif k in {"aktif","status"}: new = "aktif"
        elif k in {"catatan","keterangan"}: new = "catatan"
        else: new = raw
        ren[c] = new
    out = df.rename(columns=ren).copy()
    for c in out.columns:
        if out[c].dtype == "object":
            out[c] = out[c].astype(str).map(_clean_text)
    return out

# ===== Load data =====
hakim_df, pp_df, js_df, js_ghoib_df, libur_df, rekap_df, sk_df_db = load_with_sk()

# ==== Resolve SK (pakai DB, fallback CSV ./data) ====
def _load_sk_fallback_from_csv() -> tuple[pd.DataFrame, str]:
    data_dir = Path.cwd() / "data"
    candidates = [data_dir / n for n in ("sk_df.csv","sk_majelis.csv","sk.csv")]
    if data_dir.exists():
        for p in data_dir.glob("*.csv"):
            if "sk" in p.name.lower() and p not in candidates:
                candidates.append(p)
    for p in candidates:
        try:
            if p.exists():
                df = pd.read_csv(p, encoding="utf-8-sig")
                df = _standardize_cols(df)
                if "ketua" in df.columns:
                    return df, str(p)
        except Exception:
            pass
    return pd.DataFrame(), ""

sk_src = "DB"
sk_resolved = _standardize_cols(sk_df_db if isinstance(sk_df_db, pd.DataFrame) else pd.DataFrame())
if sk_resolved.empty or "ketua" not in sk_resolved.columns:
    sk_csv, csv_path = _load_sk_fallback_from_csv()
    if not sk_csv.empty:
        sk_resolved, sk_src = sk_csv, f"CSV: {csv_path}"

if "_sk_resolved" not in st.session_state:
    st.session_state["_sk_resolved"] = sk_resolved
    st.session_state["_sk_src"] = sk_src
else:
    if st.session_state.get("_sk_resolved", pd.DataFrame()).empty and not sk_resolved.empty:
        st.session_state["_sk_resolved"] = sk_resolved
        st.session_state["_sk_src"] = sk_src

sk_df = st.session_state.get("_sk_resolved", pd.DataFrame())
sk_src = st.session_state.get("_sk_src", sk_src)
st.caption(f"🗂️ Sumber SK saat ini: **{sk_src}**")

# ===== Pilih ketua by beban aktif + ambil baris SK =====
def _best_sk_row_for_ketua(sk: pd.DataFrame, ketua: str) -> pd.Series | None:
    if sk is None or sk.empty or not ketua: return None
    df = _standardize_cols(sk)
    if "ketua" not in df.columns: return None
    df["__ketua_key"] = df["ketua"].astype(str).map(_name_key)
    df["__ketua_tok"] = df["__ketua_key"].map(lambda s: set(s.split()))
    target = _tokset(ketua)
    if not target: return None
    cand = df[df["__ketua_tok"].apply(lambda s: len(s & target) > 0)].copy()
    if cand.empty:
        key = _name_key(ketua)
        cand = df[df["__ketua_key"] == key].copy()
        if cand.empty:
            return None
    cand["__overlap"] = cand["__ketua_tok"].apply(lambda s: len(s & target))
    cand["__aktif"] = df.get("aktif", pd.Series([True]*len(df))).apply(_is_active_value) if "aktif" in df.columns else True
    cand["__rank"] = df.get("majelis", pd.Series([""]*len(df))).astype(str).map(_majelis_rank) if "majelis" in df.columns else 10**9
    cand = cand.sort_values(["__aktif","__overlap","__rank"], ascending=[False, False, True], kind="stable")
    return cand.iloc[0]

def _pick_ketua_by_beban(hakim_df: pd.DataFrame, rekap_df: pd.DataFrame) -> tuple[str, pd.Series | None]:
    if hakim_df is None or hakim_df.empty or "nama" not in hakim_df.columns:
        return "", None
    df = hakim_df.copy()
    df["__aktif"] = df.get("aktif", 1).apply(_is_active_value)
    df = df[df["__aktif"] == True]
    if df.empty: return "", None
    counts = {}
    if isinstance(rekap_df, pd.DataFrame) and not rekap_df.empty and "hakim" in rekap_df.columns:
        counts = rekap_df["hakim"].astype(str).str.strip().value_counts().to_dict()
    df["__load"] = df["nama"].astype(str).str.strip().map(lambda n: int(counts.get(n, 0)))
    df = df.sort_values(["__load","nama"], kind="stable").reset_index(drop=True)
    ketua = str(df.iloc[0]["nama"])
    sk_row = _best_sk_row_for_ketua(sk_df, ketua)
    return ketua, sk_row

# ===== PP/JS: pair 4-step, ROTATE hanya saat SIMPAN =====
def _pair_combos_from_sk(sk_row: pd.Series) -> list[tuple[str,str]]:
    if not isinstance(sk_row, pd.Series): return []
    p1 = str(sk_row.get("pp1","")).strip()
    p2 = str(sk_row.get("pp2","")).strip()
    j1 = str(sk_row.get("js1","")).strip()
    j2 = str(sk_row.get("js2","")).strip()
    pp_opts = [x for x in [p1, p2] if x]
    js_opts = [x for x in [j1, j2] if x]
    combos: list[tuple[str,str]] = []
    if pp_opts and js_opts:
        order = [(0,0),(1,0),(0,1),(1,1)]
        for ip, ij in order:
            if ip < len(pp_opts) and ij < len(js_opts):
                combos.append((pp_opts[ip], js_opts[ij]))
    elif pp_opts:
        combos = [(pp_opts[0], "")]
        if len(pp_opts) > 1: combos.append((pp_opts[1], ""))
    elif js_opts:
        combos = [("", js_opts[0])]
        if len(js_opts) > 1: combos.append(("", js_opts[1]))
    else:
        combos = []
    dedup = []
    for t in combos:
        if not dedup or dedup[-1] != t:
            dedup.append(t)
    return dedup or [("", "")]

def _peek_pair(ketua: str, sk_row: pd.Series, jenis: str, rekap_df: pd.DataFrame) -> tuple[str,str]:
    combos = _pair_combos_from_sk(sk_row)
    key = f"rrpair_{_name_key(ketua)}"
    idx = int(st.session_state.get(key, 0)) % len(combos)
    pp, js = combos[idx]
    if str(jenis).strip().upper() == "GHOIB":
        js_gh = choose_js_ghoib_db(rekap_df, use_aktif=True)
        if js_gh: js = js_gh
    return pp, js

def _consume_pair_on_save_once(ketua: str, sk_row: pd.Series, jenis: str, rekap_df: pd.DataFrame) -> tuple[str,str]:
    combos = _pair_combos_from_sk(sk_row)
    key = f"rrpair_{_name_key(ketua)}"
    cur = int(st.session_state.get(key, 0)) % len(combos)
    pp, js = combos[cur]
    if str(jenis).strip().upper() == "GHOIB":
        js_gh = choose_js_ghoib_db(rekap_df, use_aktif=True)
        if js_gh: js = js_gh
    st.session_state[key] = (cur + 1) % len(combos)
    return pp, js

# ===== Tanggal Sidang (strict) =====
def _weekday_num_from_map(hari_text: str) -> int:
    try: return int(HARI_MAP.get(str(hari_text), 0))
    except Exception: return 0

def _next_judge_day_strict(start_date: date, hari_sidang_num: int, libur_set: set[str]) -> date:
    if not isinstance(start_date, (date, datetime)) or not hari_sidang_num:
        return start_date
    target_py = (hari_sidang_num - 1) % 7  # Mon=0..Sun=6
    d0 = start_date if isinstance(start_date, date) else start_date.date()
    for i in range(0, 120):
        d = d0 + timedelta(days=i)
        if d.weekday() != target_py:
            continue
        if str(d) in libur_set:
            continue
        return d
    return d0

def compute_tgl_sidang(base: date, jenis: str, hari_sidang_num: int, libur_set: set[str], klasifikasi: str = "") -> date:
    J = str(jenis).strip().upper()
    K = str(klasifikasi).strip().upper()
    if J == "BIASA":
        start = base + timedelta(days=8)
        end_cap = base + timedelta(days=14)
        d = _next_judge_day_strict(start, hari_sidang_num, libur_set)
        if d <= end_cap:
            return d
        return _next_judge_day_strict(end_cap, hari_sidang_num, libur_set)
    elif J == "ISTBAT":
        start = base + timedelta(days=21)
        return _next_judge_day_strict(start, hari_sidang_num, libur_set)
    elif J == "GHOIB":
        off = 124 if K in {"CT", "CG"} else 31
        start = base + timedelta(days=off)
        return _next_judge_day_strict(start, hari_sidang_num, libur_set)
    elif J == "ROGATORI":
        start = base + timedelta(days=124)
        return _next_judge_day_strict(start, hari_sidang_num, libur_set)
    elif J == "MAFQUD":
        start = base + timedelta(days=246)
        return _next_judge_day_strict(start, hari_sidang_num, libur_set)
    return base

# ===== Helper dropdown dari master PP/JS =====
def _options_from_master(df: pd.DataFrame, prefer_active=True) -> list[str]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    # ambil kolom nama yang paling mungkin
    name_col = None
    for c in ["nama", "pp", "js", "nama_lengkap", "Nama", "NAMA"]:
        if c in df.columns:
            name_col = c
            break
    if not name_col:
        return []
    x = df[[name_col]].copy()
    x[name_col] = x[name_col].astype(str).str.strip()
    x = x[x[name_col] != ""]
    # prioritas aktif kalau ada kolom aktif
    if prefer_active and "aktif" in df.columns:
        df["_aktif__"] = df["aktif"].apply(_is_active_value)
        x = x.join(df["_aktif__"])
        x = x.sort_values(by=["_aktif__", name_col], ascending=[False, True])
        names = x[name_col].tolist()
    else:
        names = sorted(x[name_col].unique().tolist())
    # buang duplikat sambil pertahankan urutan
    seen, out = set(), []
    for n in names:
        if n not in seen:
            seen.add(n); out.append(n)
    return out

# ===== Form input — AUTO CLEAR (no widget keys) =====
left, right = st.columns([2, 1])
with st.form("form_perkara", clear_on_submit=True):
    with left:
        nomor = st.text_input("Nomor Perkara")
        tgl_register_input = st.date_input("Tanggal Register", value=date.today())
        KLAS_OPTS = ["CG","CT","VERZET","PAW","WARIS","ISTBAT","HAA","Dispensasi","Poligami","Maqfud","Asal Usul","Perwalian","Harta Bersama","EkSya","Lain-Lain","Lainnya (ketik)"]
        klas_sel = st.selectbox("Klasifikasi Perkara", KLAS_OPTS, index=0)
        klas_final = st.text_input("Tulis klasifikasi lainnya") if klas_sel == "Lainnya (ketik)" else klas_sel
        jenis = st.selectbox("Jenis Perkara (Proses)", ["Biasa","ISTBAT","GHOIB","ROGATORI","MAFQUD"])
    with right:
        metode_input = st.selectbox("Metode", ["E-Court","Manual"], index=0)


        # Ketua (aktif diprioritaskan)
        semua_nama = []
        if isinstance(hakim_df, pd.DataFrame) and "nama" in hakim_df.columns:
            df_sorted = hakim_df.copy()
            df_sorted["__aktif_rank"] = (~df_sorted.get("aktif",1).apply(_is_active_value)).astype(int)
            df_sorted = df_sorted.sort_values(["__aktif_rank","nama"], kind="stable")
            semua_nama = df_sorted["nama"].dropna().astype(str).tolist()
        hakim_manual = st.selectbox("Ketua (opsional, override otomatis)", [""] + semua_nama)

        # === Dropdown PP & JS dari master ===
        pp_opts = _options_from_master(pp_df, prefer_active=True)
        js_opts = _options_from_master(js_df, prefer_active=True)
        pp_manual = st.selectbox("PP Manual (opsional)", [""] + pp_opts)
        js_manual = st.selectbox("JS Manual (opsional)", [""] + js_opts)

        tipe_pdt = st.selectbox("Tipe Perkara (Pdt)", ["Otomatis","Pdt.G","Pdt.P","Pdt.Plw"])

    # Tentukan Ketua & SK
    if str(hakim_manual).strip():
        ketua = str(hakim_manual).strip()
        sk_row = _best_sk_row_for_ketua(sk_df, ketua)
        if sk_row is None:
            st.warning("Ketua manual tidak ditemukan di SK. Anggota/PP/JS akan dikosongkan.")
    else:
        ketua, sk_row = _pick_ketua_by_beban(hakim_df, rekap_df)
    hakim = ketua or ""

    # Anggota STRICT dari baris SK
    anggota1 = str(sk_row.get("anggota1","")) if isinstance(sk_row, pd.Series) else ""
    anggota2 = str(sk_row.get("anggota2","")) if isinstance(sk_row, pd.Series) else ""
    if not isinstance(sk_row, pd.Series):
        st.info("Baris SK untuk ketua tidak ditemukan ⇒ Anggota/PP/JS dikosongkan.")
    else:
        if not (anggota1.strip() and anggota2.strip()):
            st.info("Baris SK ketua belum lengkap Anggota1/2. Lengkapi di Data SK.")

    
    # Preview PP/JS (tanpa geser rotasi)
    if str(pp_manual).strip():
        pp_preview = pp_manual.strip()
        js_preview = js_manual.strip() if str(js_manual).strip() else _peek_pair(hakim, sk_row, jenis, rekap_df)[1]
    else:
        if str(js_manual).strip():
            pp_preview = _peek_pair(hakim, sk_row, jenis, rekap_df)[0]
            js_preview = js_manual.strip()
        else:
            pp_preview, js_preview = _peek_pair(hakim, sk_row, jenis, rekap_df)

    # Hitung Tgl Sidang (strict)
    base = tgl_register_input if isinstance(tgl_register_input, (datetime, date)) else date.today()
    hari_sidang_num = 0
    if isinstance(hakim_df, pd.DataFrame) and not hakim_df.empty and hakim and "nama" in hakim_df.columns and ("hari_sidang" in hakim_df.columns or "hari" in hakim_df.columns):
        try:
            if "hari_sidang" in hakim_df.columns:
                hari_text = hakim_df.set_index("nama").loc[hakim, "hari_sidang"]
            else:
                hari_text = hakim_df.set_index("nama").loc[hakim, "hari"]
            hari_sidang_num = _weekday_num_from_map(str(hari_text))
        except Exception:
            pass
    libur_set = set()
    if isinstance(libur_df, pd.DataFrame) and "tanggal" in libur_df.columns and not libur_df.empty:
        try:
            libur_set = set(pd.to_datetime(libur_df["tanggal"], errors="coerce").dt.date.astype(str).tolist())
        except Exception:
            libur_set = set(str(x) for x in libur_df["tanggal"].astype(str).tolist())

    tgl_sidang = compute_tgl_sidang(
        base.date() if isinstance(base, datetime) else base,
        jenis, hari_sidang_num, libur_set, klasifikasi=klas_final
    )

    # Hasil Otomatis (preview)
    nomor_fmt, tipe_final = compute_nomor_tipe(nomor, klas_final, tipe_pdt)
    st.subheader("Hasil Otomatis (Preview)")
    resL, resR = st.columns(2)
    with resL:
        st.write("**Hakim (Ketua):**", hakim or "-")
        st.write("**Anggota 1**:", anggota1 or "-")
        st.write("**Anggota 2**:", anggota2 or "-")
    with resR:
        st.write("**PP**:", (pp_preview or "-"))
        st.write("**JS**:", (js_preview or "-"))
        st.markdown("**Tanggal Sidang**")
        st.markdown(f"<div style='font-size:1.4rem;font-weight:600'>{format_tanggal_id(pd.to_datetime(tgl_sidang))}</div>", unsafe_allow_html=True)

    # SIMPAN (rotasi PP/JS dieksekusi sekali di sini)
    simpan = st.form_submit_button("💾 Simpan ke Rekap", use_container_width=True, disabled=not bool(hakim))
    if simpan:
        pair_pp, pair_js = _consume_pair_on_save_once(hakim, sk_row, jenis, rekap_df)
        pp_val = pp_manual.strip() if str(pp_manual).strip() else pair_pp
        js_val = js_manual.strip() if str(js_manual).strip() else pair_js
        tgl_sidang_final = compute_tgl_sidang(
            base.date() if isinstance(base, datetime) else base,
            jenis, hari_sidang_num, libur_set, klasifikasi=klas_final
        )
        new_row = {
            "nomor_perkara": nomor_fmt,
            "tgl_register": pd.to_datetime(base),
            "klasifikasi": klas_final,
            "jenis_perkara": jenis,
            "metode": metode_input,
            "hakim": hakim,
            "anggota1": anggota1, "anggota2": anggota2,
            "pp": pp_val, "js": js_val,
            "tgl_sidang": pd.to_datetime(tgl_sidang_final)
        }
        tmp_df = pd.concat([rekap_df, pd.DataFrame([new_row])], ignore_index=True)
        save_table(tmp_df, "rekap")
        st.toast(f"Tersimpan! (PP/JS: {pp_val or '-'} / {js_val or '-'})", icon="✅")
        st.rerun()

# ===== Rekap (urutan masuk apa adanya) =====
st.markdown("---")
st.subheader("Rekap (berdasarkan Tanggal Register)")

def _fmt_id(x):
    dt = pd.to_datetime(x, errors="coerce")
    return format_tanggal_id(dt) if pd.notna(dt) else "-"

if isinstance(rekap_df, pd.DataFrame) and not rekap_df.empty:
    tmp = rekap_df.copy()
    need = ["nomor_perkara","jenis_perkara","hakim","anggota1","anggota2","pp","js","tgl_register","tgl_sidang"]
    for c in need:
        if c not in tmp.columns:
            tmp[c] = pd.NaT if c in ("tgl_register","tgl_sidang") else ""
    tmp["tgl_register"] = pd.to_datetime(tmp["tgl_register"], errors="coerce")
    tmp["tgl_sidang"]   = pd.to_datetime(tmp["tgl_sidang"], errors="coerce")

    default_day = (pd.to_datetime(tmp["tgl_register"].max()).date()
                   if pd.notna(tmp["tgl_register"].max()) else date.today())
    filter_date = st.date_input("Tanggal", value=default_day)
    df_filtered = tmp.loc[tmp["tgl_register"].dt.date == filter_date].copy()

    COLS = [2.6, 1.6, 1.0, 2.2, 2.2, 2.2, 1.8, 1.8, 1.6]
    h = st.columns(COLS)
    h[0].markdown("**Nomor Perkara**")
    h[1].markdown("**Register (ID)**")
    h[2].markdown("**Jenis**")
    h[3].markdown("**Hakim (Ketua)**")
    h[4].markdown("**Anggota 1**")
    h[5].markdown("**Anggota 2**")
    h[6].markdown("**PP**")
    h[7].markdown("**JS**")
    h[8].markdown("**Tgl Sidang (ID)**")
    st.markdown("<hr/>", unsafe_allow_html=True)

    if df_filtered.empty:
        st.info("Tidak ada perkara pada tanggal tersebut.")
    else:
        for _, r in df_filtered.iterrows():
            c = st.columns(COLS)
            c[0].write(str(r.get("nomor_perkara", "")) or "-")
            c[1].write(_fmt_id(r.get("tgl_register")))
            c[2].write(str(r.get("jenis_perkara", "")) or "-")
            c[3].write(str(r.get("hakim", "")) or "-")
            c[4].write(str(r.get("anggota1", "")) or "-")
            c[5].write(str(r.get("anggota2", "")) or "-")
            c[6].write(str(r.get("pp", "")) or "-")
            c[7].write(str(r.get("js", "")) or "-")
            c[8].write(_fmt_id(r.get("tgl_sidang")))
else:
    st.info("Belum ada data rekap.")
