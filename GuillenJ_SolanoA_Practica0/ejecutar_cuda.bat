@echo off
REM Ejecuta C++ secuencial y CUDA C.
REM Uso: ejecutar_cuda.bat
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Falta .venv. Revise EJECUCION.md.
    exit /b 1
)
set "PY=.venv\Scripts\python.exe"

echo [1/3] Preparando imagenes...
%PY% scripts\preparar_imagenes.py || exit /b 1

echo [2/3] Compilando C++ secuencial y CUDA C...
call "%~dp0compilar.bat" || exit /b 1

echo [3/3] Ejecutando experimentos C++ secuencial y CUDA C...
.\convolucion.exe || exit /b 1

echo.
echo Ejecución CUDA terminada. Revise la carpeta resultados.
