@echo off
REM Ejecuta Python secuencial y PyCUDA.
REM Uso: ejecutar_pycuda.bat
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Falta .venv. Revise EJECUCION.md.
    exit /b 1
)
set "PY=.venv\Scripts\python.exe"

echo [1/7] Preparando imagenes...
%PY% scripts\preparar_imagenes.py || exit /b 1
echo [2/7] Compilando referencias C++ y CUDA C...
call scripts\compilar_referencia.bat || exit /b 1
echo [3/7] Generando referencias...
%PY% -m scripts.generar_referencias || exit /b 1
echo [4/7] Registrando entorno y ejecutando pruebas...
call scripts\entorno_vs.bat || exit /b 1
%PY% -m scripts.registrar_entorno || exit /b 1
%PY% -m pytest || exit /b 1
echo [5/7] Validando resultados...
%PY% main.py validar || exit /b 1
echo [6/7] Midiendo Python y PyCUDA...
%PY% -m scripts.medir_python_pycuda || exit /b 1
echo [7/7] Generando gráficas...
%PY% scripts\generar_graficas.py
