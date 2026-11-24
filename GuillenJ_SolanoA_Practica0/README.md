# Convolución de imágenes de alta resolución: C++, CUDA C, Python y PyCUDA

Prácticas 01 y 02 de Computación Paralela, Universidad Politécnica Salesiana.
Juan Alberto Guillén · Ariel Solano.

## Resumen del proyecto

El proyecto aplica tres filtros de convolución a imágenes en escala de grises de
2000×2000, 4000×4000 y 6000×6000 píxeles:

- **Media k×k** (k = 3, 9, 21): suaviza la imagen; cada coeficiente vale 1/(k·k).
- **Nitidez 3×3** `[0,−1,0; −1,5,−1; 0,−1,0]`: realza detalles y contornos.
- **Laplaciano 3×3** `[0,1,0; 1,−4,1; 0,1,0]`: deja solo los bordes.

El mismo cálculo se implementa en cuatro versiones y se compara su resultado y su tiempo:

| Versión | Dónde calcula | Programa anfitrión | Código |
|---|---|---|---|
| C++ secuencial | CPU, un núcleo | C++ | `src/secuencial_c/`, `convolucionCPU` en `src/filtros.cu` |
| CUDA C | GPU, un hilo por píxel | C++ | `src/cuda_c/`, kernel `convolucionGPU` en `src/filtros.cu` |
| Python secuencial | CPU, un núcleo | Python | `src/python/` (bucles explícitos, sin vectorizar) |
| PyCUDA | GPU, un hilo por píxel | Python | `src/pycuda/`, kernel en `src/pycuda/kernels/convolucion.cu` |

- **Práctica 01** hizo C++ secuencial y CUDA C.
- **Práctica 02** migró el programa anfitrión a Python y ejecuta **el mismo kernel CUDA C** desde Python con PyCUDA (`SourceModule`, `mem_alloc`, `memcpy_htod`/`memcpy_dtoh`, bloques e hilos explícitos).

Las cuatro versiones usan los mismos datos en float32, extensión con ceros en los bordes y arreglos de entrada y salida separados. Se validan contra C++ secuencial:
- con una matriz 5×5 calculada a mano,
- con una imagen de 1013×757 que no es múltiplo de los hilos por bloque,
- comparando las salidas completas.

Experimentos (un factor a la vez):

| Experimento | Configuración | Versiones |
|---|---|---|
| Filtro | Media, nitidez y laplaciano 3×3; 4000×4000 | Las cuatro |
| Resolución | Media 9×9; 2000², 4000², 6000² | Las cuatro |
| Máscara | Media 3×3, 9×9, 21×21; 4000×4000 | Las cuatro |
| Hilos por bloque | Media 9×9; 4000×4000; 128, 256, 512 | CUDA C y PyCUDA |

Cómo se mide la GPU:
- Se calienta 2 s antes de medir y se repite 10 veces cada configuración (Python secuencial, 5 veces).
- Eventos CUDA separan la copia CPU→GPU, el kernel y la copia GPU→CPU.

Python secuencial tiene un límite de 120 s por ejecución. Si no termina, la configuración se registra como «no completada», sin estimar su tiempo.

El análisis completo está en `../docs/informe/informe_practica02.pdf` y la presentación en `../docs/presentacion/presentacion_practica02.pdf`.

## Estructura

```
GuillenJ_SolanoA_Practica0/
├── ejecutar_cuda.bat          # versión C++ secuencial + CUDA C
├── ejecutar_pycuda.bat        # versión Python secuencial + PyCUDA
├── ejecutar_paralelo.bat      # 4 experimentos solo con CUDA C + PyCUDA, cualquier imagen
├── generar_documentos.bat     # informe y presentación (aparte)
├── compilar.bat               # compila convolucion.exe (C++ y CUDA C)
├── main.cu / main.py          # programas principales en C++ y en Python
├── requirements.txt           # dependencias con versión fija
├── requirements-documentos.txt
├── datos/                     # imágenes de entrada (.pgm) y hashes SHA-256
├── imagenes/ImagenGrande.jpg  # imagen original de la que salen los .pgm
├── src/
│   ├── filtros.cu, imagenes.cpp, experimentos.cu, configuracion.h   # base C/CUDA
│   ├── filtros/               # máscaras (C++)
│   ├── secuencial_c/          # C++ secuencial
│   ├── cuda_c/                # CUDA C y referencia.cu (exporta salidas float32)
│   ├── python/                # Python secuencial, imágenes, máscaras, configuración
│   └── pycuda/                # contexto CUDA, lanzamiento del kernel y kernel .cu
├── scripts/                   # preparación, referencias, mediciones, gráficas, documentos
├── tests/                     # pytest: prueba manual, máscaras, tipos, GPU
└── resultados/
    ├── mediciones/            # mediciones.csv, mediciones_python_pycuda.csv, entorno.json
    ├── pruebas/               # prueba manual, validación y evidencia visual
    ├── imagenes/              # salidas de los filtros
    ├── graficas/
    ├── referencias/           # salidas float32 (.bin) para comparar (no se suben a git)
    └── paralelo/<imagen>/     # 4 experimentos de ejecutar_paralelo.bat
```

## Requisitos

- Windows 10/11.
- GPU NVIDIA con controlador actualizado. El código se compila para `sm_86` (RTX 30xx). Con otra GPU, cambie `-arch=sm_86` en `compilar.bat` y `scripts/compilar_referencia.bat`, y `ARQUITECTURA` en `src/python/comun/configuracion.py`.
- CUDA Toolkit 12.9 (`nvcc`).
- Visual Studio 2022 con «Desarrollo para el escritorio con C++». Los `.bat` cargan `cl.exe` con `scripts/entorno_vs.bat`.
- Python 3.12.
- Microsoft Word y PowerPoint, solo para exportar el informe y la presentación a PDF.

## Instalación

Desde la carpeta `GuillenJ_SolanoA_Practica0/`, en PowerShell:

```powershell
py -3.12 -m venv .venv
cmd /c "call scripts\entorno_vs.bat && .venv\Scripts\python.exe -m pip install -r requirements.txt"
```

Para generar también el informe y la presentación:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-documentos.txt
```

## Ejecución

Todos los comandos se ejecutan desde `GuillenJ_SolanoA_Practica0/`.

### 1. Versión C/C++ y CUDA C

```powershell
.\ejecutar_cuda.bat
```

Prepara las imágenes, compila `convolucion.exe` (`nvcc -O3 -arch=sm_86`) y ejecuta:
- la prueba manual,
- la prueba de no múltiplo,
- los experimentos, con C++ secuencial y CUDA C.

Escribe:
- `resultados/mediciones/mediciones.csv`
- `resultados/pruebas/prueba_manual.csv`
- `resultados/pruebas/validacion.csv`
- las imágenes `.pgm` de salida en `resultados/imagenes/`

Tarda unos 2 minutos.

### 2. Versión Python y PyCUDA

```powershell
.\ejecutar_pycuda.bat
```

Pasos:
1. Prepara las imágenes y comprueba su SHA-256.
2. Compila la herramienta de referencias C++/CUDA C y exporta sus salidas float32.
3. Registra el entorno (`entorno.json`).
4. Ejecuta las pruebas (pytest).
5. Valida las cuatro versiones (`main.py validar`).
6. Mide Python secuencial y PyCUDA (`scripts/medir_python_pycuda.py`).
7. Genera las gráficas.

Escribe:
- `resultados/mediciones/mediciones_python_pycuda.csv`
- `resultados/mediciones/inicializacion.csv`
- `resultados/pruebas/*_python_pycuda.csv`

Python secuencial es lento: la corrida completa tarda unos 25 minutos.

Para repetir solo las mediciones de PyCUDA, conservando las de Python:

```powershell
cmd /c "call scripts\entorno_vs.bat && .venv\Scripts\python.exe -m scripts.medir_python_pycuda --solo-pycuda"
```

### 3. Versión solo paralela: los 4 experimentos con CUDA C y PyCUDA

```powershell
.\ejecutar_paralelo.bat                          # imágenes de la práctica (datos\base_*.pgm)
.\ejecutar_paralelo.bat C:\ruta\foto.jpg          # cualquier imagen
.\ejecutar_paralelo.bat foto1.jpg foto2.png      # varias imágenes, una carpeta por imagen
.\ejecutar_paralelo.bat foto.jpg --resoluciones 1000,2000,3000   # otras resoluciones
```

Ejecuta los **4 experimentos de la guía**, solo con las versiones paralelas, sobre la imagen que se le dé. Acepta JPG, PNG, PGM o cualquier formato que lea Pillow.

1. **Prepara la imagen como en la práctica 01**: la pasa a escala de grises, toma el cuadrado central y lo redimensiona con Lanczos a 2000×2000, 4000×4000 y 6000×6000. Sin argumentos, usa directamente `datos/base_2000.pgm`, `base_4000.pgm` y `base_6000.pgm`.
2. **Ejecuta los experimentos**, cambiando un factor a la vez. Las configuraciones que se repiten entre experimentos se miden una sola vez:

   | Experimento | Configuración |
   |---|---|
   | Filtro | Media, nitidez y laplaciano 3×3; 4000²; 256 hilos |
   | Resolución | Media 9×9; 2000², 4000², 6000²; 256 hilos |
   | Máscara | Media 3×3, 9×9, 21×21; 4000²; 256 hilos |
   | Hilos por bloque | Media 9×9; 4000²; 128, 256, 512 hilos |

   Con `--resoluciones`, los experimentos de filtro, máscara e hilos usan la resolución intermedia.
3. **Mide CUDA C** (`src/cuda_c/referencia.exe`, el bucle de la práctica 01) **y PyCUDA** con el mismo procedimiento: 2 s de calentamiento y 10 repeticiones, con tiempos H2D, kernel, D2H y total.
4. **Compara la salida de PyCUDA con la de CUDA C**, antes del recorte a 0–255.

Todo queda en `resultados/paralelo/<nombre_imagen>/` (`imagenes_practica/` si no se pasa imagen):

| Archivo | Contenido |
|---|---|
| `mediciones.csv` | Las 10 repeticiones de cada versión y configuración (mismas columnas que `mediciones.csv`) |
| `resumen.csv` | Por experimento: medianas de H2D, kernel, D2H y total, IQR y CV del kernel, % de copias y cociente PyCUDA / CUDA C |
| `validacion.csv` | Error máximo y medio de PyCUDA frente a CUDA C, tolerancia y OK/FALLA |
| `graficas/experimento_*.png` | Una gráfica por experimento: kernel, tiempo total y reparto del tiempo en PyCUDA |
| `imagenes/` | Original y salidas de CUDA C y PyCUDA (reducidas a 1000 px y recorte central de 600×600) |
| `inicializacion.csv` | Tiempo de crear el contexto y compilar el kernel en PyCUDA |

En la consola se imprime una tabla por experimento. No usa las versiones secuenciales: tarda alrededor de 1 minuto por imagen.

### 4. Informe y presentación (aparte)

```powershell
.\generar_documentos.bat
```

Lee los CSV de `resultados/` y genera:
- `../docs/informe/informe_practica02.docx` y su `.pdf`
- `../docs/presentacion/presentacion_practica02.pptx` y su `.pdf`

Requiere haber ejecutado antes las versiones 1 y 2. Solo calcula la evidencia visual de las cuatro versiones si todavía no existe `resultados/pruebas/evidencia_visual.csv`.

### Pruebas

```powershell
.venv\Scripts\python.exe -m pytest -m "not gpu"                               # sin GPU
cmd /c "call scripts\entorno_vs.bat && .venv\Scripts\python.exe -m pytest"    # todas
```

## Trazabilidad

- Repositorio: https://github.com/JuanGuillenA/procesamiento-imagenes-pycuda
- Práctica 01: etiqueta git `practica01-entrega` (commit `08b155eab3bbc991cc9a20f9e633f25b41ac223f`).
- Las imágenes de `datos/` son las de la práctica 01; su SHA-256 está en `datos/hashes_p01.json` y se comprueba en cada ejecución de Python.
- `resultados/mediciones/entorno.json` registra el equipo, las versiones y el commit con el que se midió.
- La carpeta `resultados/mediciones/corrida_descartada_2026-11-13/` guarda una corrida GPU que se repitió: PyCUDA se calentaba con una sola ejecución. El informe lo explica.
