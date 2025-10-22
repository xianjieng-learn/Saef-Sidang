import pandas as pd
from typing import Iterable, Tuple, Any
from db import get_conn

def load_table(name: str) -> pd.DataFrame:
    con = get_conn()
    try:
        df = pd.read_sql_query(f"SELECT * FROM {name} ORDER BY id;", con)
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()

def save_table(name: str, df: pd.DataFrame):
    con = get_conn()
    try:
        cur = con.cursor()
        cur.execute("BEGIN;")
        cur.execute(f"DELETE FROM {name};")
        cols = [c for c in df.columns if c != "id"]
        df_to_write = df[cols].copy() if "id" in df.columns else df.copy()
        df_to_write = df_to_write.where(pd.notnull(df_to_write), None)
        df_to_write.to_sql(name, con, if_exists="append", index=False)
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

def upsert(table: str, columns: Iterable[str], values: Tuple[Any, ...], unique_col: str = "nama"):
    cols = list(columns)
    placeholders = ",".join(["?"] * len(cols))
    set_clause = ",".join([f"{c}=excluded.{c}" for c in cols if c != unique_col])
    sql = f"""
    INSERT INTO {table} ({",".join(cols)})
    VALUES ({placeholders})
    ON CONFLICT({unique_col}) DO UPDATE SET {set_clause};
    """
    con = get_conn()
    try:
        con.execute(sql, values)
        con.commit()
    finally:
        con.close()

def delete_by_id(table: str, row_id: int):
    con = get_conn()
    try:
        con.execute(f"DELETE FROM {table} WHERE id=?;", (row_id,))
        con.commit()
    finally:
        con.close()
