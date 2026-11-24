@echo off
REM Deja cl.exe en el PATH (vcvars64.bat de Visual Studio 2022), igual que compilar.bat de P01.
REM Uso: call scripts\entorno_vs.bat
where cl.exe >nul 2>nul && goto :listo

set "VCVARS="
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" goto :respaldo
REM vcvars64.bat tambien busca vswhere.exe en el PATH.
set "PATH=%PATH%;%ProgramFiles(x86)%\Microsoft Visual Studio\Installer"
for /f "usebackq delims=" %%i in (`call "%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VCVARS=%%i\VC\Auxiliary\Build\vcvars64.bat"

:respaldo
REM Respaldo: la misma ruta que usa compilar.bat de P01.
if not defined VCVARS set "VCVARS=C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
if not exist "%VCVARS%" goto :error
call "%VCVARS%" >nul
where cl.exe >nul 2>nul || goto :error

:listo
REM setuptools (al compilar PyCUDA con pip) debe usar este entorno ya cargado.
set DISTUTILS_USE_SDK=1
set MSSdk=1
exit /b 0

:error
echo No se encontro cl.exe. Instale Visual Studio 2022 con herramientas de C++.
exit /b 1
