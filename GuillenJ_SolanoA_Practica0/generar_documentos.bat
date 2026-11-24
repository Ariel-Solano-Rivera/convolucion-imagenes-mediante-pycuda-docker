@echo off
REM Genera el informe (Word y PDF) y la presentacion (PowerPoint y PDF) desde los CSV.
REM Requiere haber ejecutado antes ejecutar_cuda.bat y ejecutar_pycuda.bat, y tener
REM Microsoft Word y PowerPoint para exportar a PDF.
REM Salidas: ..\docs\informe\ y ..\docs\presentacion\
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Falta .venv. Revise el README.
    exit /b 1
)
set "PY=.venv\Scripts\python.exe"

if not exist resultados\pruebas\evidencia_visual.csv (
    echo [0/4] Evidencia visual de las cuatro versiones (unos 2 minutos^)...
    call scripts\entorno_vs.bat || exit /b 1
    %PY% -m scripts.evidencia_visual || exit /b 1
)
echo [1/4] Informe (Word)...
%PY% -m scripts.generar_informe || exit /b 1
echo [2/4] Presentacion (PowerPoint)...
%PY% -m scripts.generar_presentacion || exit /b 1
echo [3/4] Exportando a PDF...
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\exportar_pdf.ps1 || exit /b 1
echo [4/4] Listo. Revise ..\docs\informe y ..\docs\presentacion
