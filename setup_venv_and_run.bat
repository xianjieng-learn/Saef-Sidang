@echo off
setlocal

REM === SAEF Setup & Run (venv + install + run app.py) ===
cd /d "%~dp0"
set "APP_ENTRY=app.py"

REM Pilih launcher
set "PY=py"
where py >nul 2>nul || (set "PY=python")

if not exist ".venv" (
  echo [SETUP] Membuat virtualenv .venv ...
  %PY% -3.12 -m venv .venv || %PY% -m venv .venv
)

set "VENV_PY=.venv\Scripts\python.exe"
if not exist  (
  echo [ERROR] Tidak menemukan %VENV_PY%.
  echo Cek instalasi Python dan coba lagi.
  pause
  exit /b 1
)

echo [SETUP] Upgrade pip ...
-m pip install --upgrade pip

if exist requirements.txt (
  echo [SETUP] Install dependencies dari requirements.txt ...
  -m pip install -r requirements.txt
) else (
  echo [SETUP] Tidak ada requirements.txt, install paket minimum ...
  -m pip install streamlit pandas
)

if not exist "%APP_ENTRY%" (
  echo [ERROR] File "%APP_ENTRY%" tidak ditemukan.
  pause
  exit /b 1
)

echo.
echo [RUN] Menjalankan aplikasi: %APP_ENTRY% (virtualenv)
 -m streamlit run "%APP_ENTRY%"
if errorlevel 1 pause
