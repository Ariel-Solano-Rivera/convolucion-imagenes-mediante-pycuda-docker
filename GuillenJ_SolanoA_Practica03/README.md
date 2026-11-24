# Práctica 03 · Servicio web de convolución con Docker y PyCUDA

## Resumen

Convertimos el programa de convolución de la práctica 02 en un servicio web que procesa
imágenes en la GPU con PyCUDA y se ejecuta dentro de Docker. Incluye una interfaz web, una
API HTTP, pruebas y scripts de experimentos.

## Cómo ejecutar

Todos los comandos se ejecutan en PowerShell desde esta carpeta.

### Con Docker

Requisitos: GPU NVIDIA, Docker Desktop (con WSL2).

```powershell
docker compose build
docker compose up -d
```

- Interfaz web: **http://127.0.0.1:8080**
- Desde la línea de comandos:

  ```powershell
  curl.exe -s -F "imagen=@..\GuillenJ_SolanoA_Practica0\datos\base_2000.pgm" `
    -F filtro=media -F mascara=9 http://127.0.0.1:8080/api/convoluciones
  ```

- Detener: `docker compose down`

### Sin Docker

Requisitos: Python 3.12, CUDA Toolkit 12.9 y Visual Studio 2022 con C++.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cmd /c "..\GuillenJ_SolanoA_Practica0\scripts\entorno_vs.bat && .venv\Scripts\python.exe servidor.py"
```

Interfaz web: **http://127.0.0.1:8000**

### Pruebas y experimentos

Requieren el entorno `.venv` del apartado anterior y Docker Desktop abierto.

```powershell
.\.venv\Scripts\python.exe -m pytest      # pruebas
.\ejecutar_piloto.ps1                     # validación rápida
.\ejecutar_experimentos.ps1               # experimentos completos (requiere todo en un commit)
```

### Informe

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-documentos.txt
.\.venv\Scripts\python.exe -m scripts.generar_informe
powershell -ExecutionPolicy Bypass -File scripts\exportar_pdf.ps1
```
