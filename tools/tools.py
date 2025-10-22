# tools/salvage_csv_fragments.py
from pathlib import Path
import pandas as pd
import csv

DATA = Path("data")
OUT  = DATA / "rekap__SALVAGED.csv"

# Kumpulkan kandidat file pecahan/backup
candidates = []
candidates += sorted(DATA.glob("rekap*.tmp"))
candidates += sorted(DATA.glob("rekap*.bak"))
candidates += sorted(DATA.glob("rekap__*.bak.csv"))

def try_read(p: Path):
    # Coba multi-encoding + auto-separator
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            # engine='python' + sep=None (sniffer) + on_bad_lines='skip' untuk baris rusak
            df = pd.read_csv(
                p, encoding=enc, engine="python", sep=None, on_bad_lines="skip",
                dtype=str, quoting=csv.QUOTE_MINIMAL
            )
            if df is not None and not df.empty:
                df = df.apply(lambda s: s.str.strip() if s.dtype == "object" else s)
                return df
        except Exception:
            pass
    return pd.DataFrame()

def unify_columns(df: pd.DataFrame) -> pd.DataFrame:
    # Standarkan nama kolom umum kalau ada
    rename = {}
    for c in list(df.columns):
        k = str(c).strip().lower().replace("_"," ").replace("-", " ")
        if k in {"nomor perkara","no perkara","no. perkara","no"}:
            rename[c] = "Nomor Perkara"
        elif k in {"js","jurusita","juru sita"}:
            rename[c] = "js"
        elif k in {"jenis perkara","jenis","tipe","kategori"}:
            rename[c] = "jenis_perkara"
    if rename:
        df = df.rename(columns=rename)
    return df

def dedup(df: pd.DataFrame) -> pd.DataFrame:
    # Prioritaskan dedup pakai kolom yang paling “kunci”
    for key in ("Nomor Perkara","no_perkara","id","Nomor","No"):
        if key in df.columns:
            return df.drop_duplicates(subset=[key])
    # fallback: dedup seluruh baris
    return df.drop_duplicates()

def main():
    if not candidates:
        print("Tidak ada kandidat .tmp/.bak ditemukan di folder data/")
        return
    merged = pd.DataFrame()
    for p in candidates:
        df = try_read(p)
        if df.empty:
            continue
        df = unify_columns(df)
        merged = pd.concat([merged, df], ignore_index=True, sort=False)

    if merged.empty:
        print("Tidak ada konten yang bisa diselamatkan dari kandidat .tmp/.bak.")
        return

    merged = dedup(merged)
    # Buang baris kosong total
    merged = merged.dropna(how="all")
    # Tulis hasil salvage (tidak menimpa rekap.csv!)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"Salvaged {len(merged)} baris -> {OUT}")

if __name__ == "__main__":
    main()
