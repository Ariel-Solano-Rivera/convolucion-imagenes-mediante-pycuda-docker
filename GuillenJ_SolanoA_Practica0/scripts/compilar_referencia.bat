@echo off
REM Compila la herramienta de referencias con el mismo código unificado.
cd /d "%~dp0.."
call scripts\entorno_vs.bat || exit /b 1
set "SRC=src"
nvcc -O3 -arch=sm_86 -I%SRC% -o %SRC%\cuda_c\referencia.exe %SRC%\cuda_c\referencia.cu %SRC%\imagenes.cpp %SRC%\filtros.cu %SRC%\filtros\media.cpp %SRC%\filtros\nitidez.cpp %SRC%\filtros\laplaciano.cpp %SRC%\secuencial_c\media.cpp %SRC%\secuencial_c\nitidez.cpp %SRC%\secuencial_c\laplaciano.cpp %SRC%\cuda_c\media.cu %SRC%\cuda_c\nitidez.cu %SRC%\cuda_c\laplaciano.cu || exit /b 1
del /q %SRC%\cuda_c\referencia.exp %SRC%\cuda_c\referencia.lib 2>nul
exit /b 0
