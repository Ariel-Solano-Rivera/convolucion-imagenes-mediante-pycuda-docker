@echo off
REM Version solo paralela: los 4 experimentos (filtro, resolucion, mascara e hilos)
REM con CUDA C y PyCUDA.
REM Uso: ejecutar_paralelo.bat [imagen1.jpg imagen2.png ...] [--resoluciones 2000,4000,6000]
REM   Con imagenes: cada una se prepara como en P01 (gris, recorte cuadrado central y
REM   Lanczos a 2000, 4000 y 6000) y se ejecutan los 4 experimentos.
REM   Sin imagenes: usa datos\base_2000.pgm, base_4000.pgm y base_6000.pgm.
REM Resultados en resultados\paralelo\<nombre_imagen>\
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Falta .venv. Revise el README.
    exit /b 1
)
set "PY=.venv\Scripts\python.exe"

echo [1/3] Preparando Visual Studio (cl.exe para nvcc)...
call scripts\entorno_vs.bat || exit /b 1

echo [2/3] Compilando CUDA C (src\cuda_c\referencia.exe)...
call scripts\compilar_referencia.bat || exit /b 1

echo [3/3] Ejecutando los 4 experimentos con CUDA C y PyCUDA...
%PY% -m scripts.ejecutar_paralelo %* || exit /b 1
echo.
echo Listo. Revise resultados\paralelo\
