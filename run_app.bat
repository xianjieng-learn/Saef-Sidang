@echo off
setlocal ENABLEDELAYEDEXPANSION

REM === SAEF Streamlit Runner (app.py) ===
cd /d "%~dp0"
set "APP_ENTRY=app.py"

if not exist "%APP_ENTRY%" (
  echo [ERROR] File "%APP_ENTRY%" tidak ditemukan di folder ini.
  echo Letakkan batch ini di folder yang sama dengan %APP_ENTRY% lalu jalankan lagi.
  pause
  exit /b 1
)

REM Pilih interpreter:
set "PYCMD="
if exist ".venv\Scripts\python.exe" (
  set "PYCMD=.venv\Scripts\python.exe"
) else (
  where py >nul 2>nul && (set "PYCMD=py") || (set "PYCMD=python")
)

REM Cek apakah streamlit tersedia; kalau tidak, coba install (pakai requirements.txt kalau ada)
"%PYCMD%" -m streamlit --version >nul 2>&1
if errorlevel 1 (
  echo [INFO] Streamlit belum terpasang untuk interpreter ini: %PYCMD%
  if exist requirements.txt (
    echo [INFO] Menginstall paket dari requirements.txt ...
    "%PYCMD%" -m pip install -r requirements.txt
  ) else (
    echo [INFO] Menginstall paket minimum (streamlit, pandas) ...
    "%PYCMD%" -m pip install streamlit pandas
  )
)

echo.
echo [RUN] Menjalankan aplikasi: %APP_ENTRY%
"%PYCMD%" -m streamlit run "%APP_ENTRY%"
set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" (
  echo.
  echo [WARN] Aplikasi keluar dengan kode %EC%.
  pause
)
exit /b %EC%
