# Prácticas 01 y 02 · Convolución de imágenes en C++, CUDA C, Python y PyCUDA

## Resumen

Aplicamos filtros de convolución a imágenes en escala de grises con cuatro versiones (C++
secuencial, CUDA C, Python secuencial y PyCUDA) y comparamos sus resultados y tiempos.

## Cómo ejecutar

Requisitos: Windows, GPU NVIDIA, CUDA Toolkit 12.9, Visual Studio 2022 con C++ y Python 3.12.

Todos los comandos se ejecutan en PowerShell desde esta carpeta.

### Instalación

```powershell
py -3.12 -m venv .venv
cmd /c "call scripts\entorno_vs.bat && .venv\Scripts\python.exe -m pip install -r requirements.txt"
```

### Ejecución

```powershell
.\ejecutar_cuda.bat          # C++ secuencial y CUDA C
.\ejecutar_pycuda.bat        # Python secuencial y PyCUDA
.\ejecutar_paralelo.bat      # solo CUDA C y PyCUDA (acepta una imagen propia: .\ejecutar_paralelo.bat foto.jpg)
```

### Pruebas

```powershell
cmd /c "call scripts\entorno_vs.bat && .venv\Scripts\python.exe -m pytest"
```

### Informe y presentación

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-documentos.txt
.\generar_documentos.bat
```
