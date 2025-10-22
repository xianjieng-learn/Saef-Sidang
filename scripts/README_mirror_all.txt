# Write-through mirror for ALL pages (CSV sync)
Let every data page write its DataFrame to a CSV **automatically** after a successful update,
so any component that still reads CSV gets the latest data.

## 1) Files
- `app_core/mirror_all.py` — helper functions for all tables:
  - `mirror_hakim_csv(df)`, `mirror_pp_csv(df)`, `mirror_js_csv(df)`, `mirror_js_ghoib_csv(df)`,
    `mirror_libur_csv(df)`, `mirror_sk_csv(df)`, `mirror_rekap_csv(df)`
  - paths default to `data/*_df.csv` (change in `DEFAULTS` dict if needed)
  - atomic writes, `utf-8-sig` encoding (Excel-friendly)

## 2) How to wire each page
Call the mirror function AFTER you commit the change to DB and reload the DataFrame.

### 3a_🧑‍⚖️_Data_Hakim.py
```python
from app_core.ss import set_df                   # optional session bridge
from app_core.mirror_all import mirror_hakim_csv
# ... after insert/update/delete & reload hakim_df ...
set_df("hakim_df", hakim_df)                     # optional
mirror_hakim_csv(hakim_df)                       # -> data/hakim_df.csv
```

### 3b_🧑‍💼_Data_PP.py
```python
from app_core.ss import set_df
from app_core.mirror_all import mirror_pp_csv
# ... after update & reload pp_df ...
set_df("pp_df", pp_df)
mirror_pp_csv(pp_df)                             # -> data/pp_df.csv
```

### 3c_🧑‍💻_Data_JS.py
```python
from app_core.ss import set_df
from app_core.mirror_all import mirror_js_csv
# ... after update & reload js_df ...
set_df("js_df", js_df)
mirror_js_csv(js_df)                             # -> data/js_df.csv
```

### 3d_🧙_Data_JS_Ghoib.py
```python
from app_core.ss import set_df
from app_core.mirror_all import mirror_js_ghoib_csv
# ... after update & reload js_ghoib_df ...
set_df("js_ghoib_df", js_ghoib_df)
mirror_js_ghoib_csv(js_ghoib_df)                 # -> data/js_ghoib_df.csv
```

### 3e_📅_Data_Libur.py
```python
from app_core.ss import set_df
from app_core.mirror_all import mirror_libur_csv
# ... after update & reload libur_df ...
set_df("libur_df", libur_df)
mirror_libur_csv(libur_df)                       # -> data/libur_df.csv
```

### 3f_🧾_Data_SK_Majelis.py
```python
from app_core.ss import set_df
from app_core.mirror_all import mirror_sk_csv
# ... after update & reload sk_df ...
set_df("sk_df", sk_df)
mirror_sk_csv(sk_df)                             # -> data/sk_df.csv
```

### 1_📥_Input_&_Hasil.py (opsional untuk rekap)
Jika kamu ingin CSV rekap selalu ikut terbaru setiap klik "Simpan ke Rekap":

```python
from app_core.mirror_all import mirror_rekap_csv

# pada saat menyimpan:
tmp_df = pd.concat([rekap_df, pd.DataFrame([new_row])], ignore_index=True)
save_table(tmp_df, "rekap")
mirror_rekap_csv(tmp_df)                         # -> data/rekap_df.csv
st.success("Tersimpan!"); st.rerun()
```

## 3) Ubah lokasi CSV (opsional)
Edit dict `DEFAULTS` di `app_core/mirror_all.py`:
```python
DEFAULTS["hakim"] = r"Z:/1.SAEF/streamlit/data/hakim_df.csv"
# dst...
```

## 4) Tips
- Fungsi mirror melakukan strip ringan pada kolom `nama` (kalau ada), lainnya dibiarkan apa adanya (termasuk gelar/tanda baca).
- Penulisan file bersifat **atomik** agar meminimalkan risiko file korup.
- Semua CSV ditulis `utf-8-sig` supaya enak dibuka di Excel Windows.
