# db.py — MySQL/MariaDB backend for SAEF
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path

import pymysql
from pymysql.cursors import DictCursor

# Streamlit opsional (supaya modul ini bisa dipakai juga di luar Streamlit)
try:
    import streamlit as st  # type: ignore
except Exception:
    st = None  # type: ignore


# ------------------------------------------------------------
# Konfigurasi: baca dari ENV (DB_* lebih diprioritaskan), lalu MYSQL_*, lalu st.secrets
# ------------------------------------------------------------
def _get_secret(name: str, default=None):
    if st is not None:
        # st.secrets bisa raise KeyError; jadi amanin
        try:
            return st.secrets.get(name, default)  # type: ignore[attr-defined]
        except Exception:
            return default
    return default

def _env(key: str, default=None):
    val = os.getenv(key, None)
    return val if val not in (None, "") else default

DB_HOST = (
    _env("DB_HOST")
    or _env("MYSQL_HOST")
    or _get_secret("DB_HOST", _get_secret("MYSQL_HOST", "127.0.0.1"))
)
DB_PORT = int(
    _env("DB_PORT", _env("MYSQL_PORT", _get_secret("DB_PORT", _get_secret("MYSQL_PORT", 3306))))
)
DB_USER = (
    _env("DB_USER")
    or _env("MYSQL_USER")
    or _get_secret("DB_USER", _get_secret("MYSQL_USER", "saefapp"))
)
DB_PASSWORD = (
    _env("DB_PASSWORD")
    or _env("MYSQL_PASS")
    or _env("MYSQL_PASSWORD")
    or _get_secret("DB_PASSWORD", _get_secret("MYSQL_PASS", _get_secret("MYSQL_PASSWORD", "")))
)
DB_NAME = (
    _env("DB_NAME")
    or _env("MYSQL_DB")
    or _get_secret("DB_NAME", _get_secret("MYSQL_DB", "saef"))
)

# Direktori app (kalau butuh simpan cache/file pendukung lain)
try:
    from platformdirs import user_data_dir  # type: ignore
    APP_DIR = Path(user_data_dir("SAEF-Sidang", "YourOrg"))
except Exception:
    APP_DIR = Path.home() / ".saef_sidang"
APP_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------
# Helper debug: tampilkan target koneksi (tanpa password)
# ------------------------------------------------------------
def debug_db_target():
    msg = f"🔌 DB target: {DB_USER}@{DB_HOST}:{DB_PORT} / db={DB_NAME}"
    if st is not None:
        st.caption(msg)
    else:
        print(msg)


# ------------------------------------------------------------
# Koneksi DB
# ------------------------------------------------------------
def get_conn() -> pymysql.connections.Connection:
    """
    Return koneksi pymysql. Caller bertanggung jawab menutup (con.close()).
    """
    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        autocommit=False,
        charset="utf8mb4",
        cursorclass=DictCursor,  # enak untuk fetchone() -> dict
        connect_timeout=3,
        read_timeout=10,
        write_timeout=10,
    )
    # Set mode strict supaya invalid value langsung error (lebih aman)
    with conn.cursor() as cur:
        cur.execute("SET SESSION sql_mode = 'STRICT_ALL_TABLES';")
        cur.execute("SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;")
    return conn


# ------------------------------------------------------------
# Bootstrap schema
# ------------------------------------------------------------
def init_db() -> None:
    """
    Buat semua tabel yang dibutuhkan kalau belum ada.
    Idempotent: aman dipanggil berulang kali.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # hakim
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS hakim (
                  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
                  nama VARCHAR(128) NOT NULL UNIQUE,
                  hari VARCHAR(64),
                  aktif TINYINT(1) DEFAULT 1,
                  max_per_hari INT,
                  catatan TEXT,
                  alias VARCHAR(128),
                  jabatan VARCHAR(128)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )

            # pp
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS pp (
                  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
                  nama VARCHAR(128) NOT NULL UNIQUE,
                  aktif TINYINT(1) DEFAULT 1,
                  catatan TEXT,
                  alias VARCHAR(128)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )

            # js
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS js (
                  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
                  nama VARCHAR(128) NOT NULL UNIQUE,
                  aktif TINYINT(1) DEFAULT 1,
                  catatan TEXT,
                  alias VARCHAR(128)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )

            # js_ghoib (opsional untuk beban GHOIB dinamis)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS js_ghoib (
                  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
                  nama VARCHAR(128) NOT NULL UNIQUE,
                  total_ghoib INT DEFAULT 0
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )

            # libur (kalender libur nasional/lokal)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS libur (
                  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
                  tanggal DATE NOT NULL UNIQUE,
                  keterangan VARCHAR(255)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )

            # SK Majelis (satu baris per majelis)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sk_majelis (
                  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
                  majelis VARCHAR(128) NOT NULL UNIQUE,
                  hari VARCHAR(64),
                  ketua VARCHAR(128),
                  anggota1 VARCHAR(128),
                  anggota2 VARCHAR(128),
                  pp1 VARCHAR(128),
                  pp2 VARCHAR(128),
                  js1 VARCHAR(128),
                  js2 VARCHAR(128),
                  aktif TINYINT(1) DEFAULT 1,
                  KEY ix_hari (hari),
                  KEY ix_ketua (ketua)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )

            # Rekap perkara
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS rekap (
                  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
                  nomor_perkara VARCHAR(64) NOT NULL UNIQUE,
                  tgl_register DATE NULL,
                  klasifikasi VARCHAR(64),
                  jenis_perkara VARCHAR(64),
                  metode VARCHAR(32),
                  hakim VARCHAR(128),
                  anggota1 VARCHAR(128),
                  anggota2 VARCHAR(128),
                  pp VARCHAR(128),
                  js VARCHAR(128),
                  tgl_sidang DATE NULL,
                  tgl_sidang_override TINYINT(1) NOT NULL DEFAULT 0,
                  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                  KEY ix_tgl_reg (tgl_register),
                  KEY ix_tgl_sidang (tgl_sidang),
                  KEY ix_hakim (hakim)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )

            # Token rotasi PP/JS per ketua (round-robin)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS rrpair_token (
                  rrkey VARCHAR(190) PRIMARY KEY,
                  idx   INT NOT NULL DEFAULT 0,
                  meta  JSON
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )

        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------
# (Opsional) fungsi util kecil
# ------------------------------------------------------------
def ping_ok() -> bool:
    """Tes koneksi cepat; True kalau bisa ping server."""
    try:
        conn = get_conn()
        try:
            conn.ping(reconnect=True)
            return True
        finally:
            conn.close()
    except Exception:
        return False
