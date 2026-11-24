# Práctica 03 · Servicio web de convolución con Docker y PyCUDA

Aplicación web que reutiliza, sin modificarlo, el kernel PyCUDA propio de la práctica 02.
Permite cargar una imagen, escoger media (3×3, 9×9 o 21×21), nitidez 3×3 o laplaciano 3×3,
procesarla en una GPU NVIDIA, ver original y resultado, y descargar el resultado.

## Continuidad con la práctica 02

| Elemento | Valor |
|---|---|
| Repositorio de la práctica 03 (este) | https://github.com/Ariel-Solano-Rivera/convolucion-imagenes-mediante-pycuda-docker |
| Repositorio de la práctica 02 | `https://github.com/JuanGuillenA/procesamiento-imagenes-pycuda` |
| Commit de origen de la práctica 02 | `1726b43d8dc8078bee7b8e679c29b0049e0f707f` |
| Carpeta de la práctica 02 (referencia ejecutable directa) | `../GuillenJ_SolanoA_Practica0/`, idéntica a la de ese commit |
| Commit de la práctica 03 medido | el registrado en `resultados/mediciones/entorno_*_final.json` y en la etiqueta de la imagen Docker |
| Kernel reutilizado | `../GuillenJ_SolanoA_Practica0/src/pycuda/kernels/convolucion.cu` (`convolucionGPU`) |
| Contexto y ejecución PyCUDA reutilizados | `src/pycuda/contexto_cuda.py`, `src/pycuda/convolucion.py` de P02 |

Se conservan: máscaras y coeficientes (media `1.0f/(k·k)` en float32, nitidez y laplaciano
de P02), datos y acumulación `float32`, extensión con ceros, un píxel de salida por hilo,
bloques e hilos solo en X (`bloques = ceil(n/256)`), y el tratamiento visual del resultado
(recorte 0–255; laplaciano `abs(x)·4`). Las imágenes de 2000², 4000² y 6000² y la de
1013×757 se leen de `../GuillenJ_SolanoA_Practica0/datos/` (SHA-256 en
`datos/hashes_p01.json` y en la columna `sha256_entrada` de cada medición).
**Lo nuevo** es solo la integración web, la cola de solicitudes, la contenerización, el
despliegue y la evaluación.

## Arquitectura

```text
navegador / cliente HTTP
   │ POST /api/convoluciones (multipart)
   ▼
Gunicorn (1 proceso, 4 hilos HTTP) ─ Flask: webapp/api.py  (solo HTTP)
   │
   ▼
webapp/procesamiento.py  (mismo pipeline en servicio y en ejecución directa)
   │ decodificación → cola acotada → trabajador CUDA único → escritura PNG/NPY
   ▼
webapp/procesador_gpu.py → código PyCUDA de P02 → GPU NVIDIA
```

- **Contexto CUDA:** se crea manualmente (sin `pycuda.autoinit`) en el único hilo
  trabajador CUDA, la primera vez que se procesa una imagen; allí mismo se compila o carga
  desde caché el kernel con `SourceModule` (`-O3`, `sm_86`). Ese tiempo se reporta aparte
  como `inicio_frio` y nunca entra en las mediciones estables. Todas las llamadas CUDA
  ocurren en ese hilo; un segundo trabajador en el mismo proceso es rechazado.
- **Memoria:** por solicitud se reservan entrada, salida (`n·4` bytes cada una) y máscara
  (`k²·4` bytes) con `cuda.mem_alloc`, y se liberan en `finally`. Su tiempo se informa
  como `reserva_liberacion` (fuera de `gpu_total`). La respuesta informa la memoria
  reservada y la memoria de GPU en uso tras reservar (`cuda.mem_get_info`).
- **Transferencias:** `memcpy_htod`/`memcpy_dtoh` síncronas desde **memoria paginable** de
  NumPy (no fijada). Eventos CUDA `e0→H2D→e1→kernel→e2→D2H→e3`, `e3.synchronize()` antes
  de leer el resultado.
- **Política de atención:** un trabajo en ejecución y uno en espera (`LIMITE_TRABAJOS_GPU=2`);
  el siguiente recibe HTTP 429 de inmediato. La espera se mide (`espera_gpu`).
- **Errores:** sin GPU, sin memoria de GPU o con fallo del kernel se responde con un código
  propio y **nunca** se calcula en CPU como sustituto. Si falla el kernel o una
  transferencia, el contexto se descarta y se vuelve a crear en la solicitud siguiente.
- **Archivos:** cada solicitud recibe un UUID y su propia carpeta; los resultados expiran a
  las 24 h (se limpian al recibir solicitudes nuevas). Las rutas de descarga solo aceptan
  UUID válidos y tres nombres fijos.

## Contrato HTTP

### `POST /api/convoluciones`

`multipart/form-data`:

| Campo | Valores |
|---|---|
| `imagen` | PNG, JPEG, BMP, PGM o PPM (se valida el formato real, no la extensión); máximo 64 MiB y 170 millones de píxeles de entrada |
| `filtro` | `media`, `nitidez` o `laplaciano` |
| `mascara` | `3`, `9` o `21` para media; `3` para nitidez y laplaciano |

Las entradas de más de 36 millones de píxeles (6000², máximo que cabe con holgura en los
8 GiB de la RTX 3070: 6000² → 275 MiB de reserva) reproducen la preparación de las
prácticas anteriores: gris, recorte cuadrado central y Lanczos hasta 6000×6000.

**201 Created** (JSON): `id_solicitud`, `filtro`, `mascara`, `dimensiones`,
`dimensiones_originales`, `preparacion`, `gpu` (`bloques`, `hilos_por_bloque`,
`memoria_reservada_mb`, `memoria_gpu_usada_mb`, `memoria_gpu_total_mb`, tipo de
transferencia), `original_url`, `resultado_url` (PNG), `resultado_crudo_url` (NumPy
`float32` previo al recorte, para validar) y `tiempos_ms`:

| Clave | Alcance (ms, `time.perf_counter` salvo indicación) |
|---|---|
| `recepcion` | lectura del cuerpo multipart en el servidor |
| `decodificacion_y_preparacion` | validación, decodificación, gris, recorte/redimensión, float32 |
| `espera_gpu` | en cola hasta que el trabajador CUDA toma el trabajo |
| `reserva_liberacion` | `mem_alloc` + `free` de los tres arreglos |
| `cpu_a_gpu`, `kernel`, `gpu_a_cpu`, `gpu_total` | eventos CUDA |
| `codificacion_y_escritura` | PNG de entrada y salida y `resultado.npy` |
| `procesamiento_total` | decodificación → escritura (lo mismo que mide la ejecución directa) |
| `servidor_total` | recepción + procesamiento total |
| `inicio_frio` | solo en la primera solicitud: importación, contexto y compilación/carga del kernel |

**Errores** (JSON `{"error": "...", "codigo": "...", "id_solicitud": "..."}`):

| HTTP | `codigo` | Causa |
|---|---|---|
| 400 | `entrada_invalida` | archivo que no es imagen, formato no admitido, dimensiones fuera de límite, filtro desconocido o máscara no permitida |
| 413 | `archivo_demasiado_grande` | cuerpo mayor que `MAX_BYTES_ARCHIVO` |
| 429 | `cola_llena` | ya hay una ejecución y una espera |
| 503 | `gpu_no_disponible` | PyCUDA/libcuda/controlador ausente, sin GPU o fallo al crear el contexto o compilar el kernel |
| 503 | `memoria_gpu_insuficiente` | `cuda.mem_alloc` no pudo reservar |
| 503 | `memoria_servidor_insuficiente` | sin RAM para decodificar |
| 500 | `error_procesamiento_gpu` | fallo de transferencia, kernel o sincronización |

### Otras rutas

- `GET /api/resultados/{uuid}/{original.png|resultado.png|resultado.npy}`: descarga.
- `GET /api/salud`: 200 con GPU, *compute capability*, memoria, versión CUDA del
  controlador y política de cola; **503** con el diagnóstico si no hay GPU utilizable.
- `GET /`: interfaz web (consume el mismo `POST`; deshabilita el botón mientras procesa).

### Consumo desde la línea de comandos

```powershell
# Windows (curl.exe incluido en Windows 10/11)
curl.exe -s -F "imagen=@..\GuillenJ_SolanoA_Practica0\datos\base_2000.pgm" `
  -F filtro=media -F mascara=9 http://127.0.0.1:8080/api/convoluciones
curl.exe -s -o resultado.png http://127.0.0.1:8080/api/resultados/<id_solicitud>/resultado.png
curl.exe -s http://127.0.0.1:8080/api/salud
```

```bash
# Linux / macOS
curl -s -F imagen=@base_2000.pgm -F filtro=laplaciano -F mascara=3 \
  http://IP_DEL_HOST:8080/api/convoluciones
```

## Docker y acceso a GPU

El **controlador NVIDIA pertenece al anfitrión** (registrado: 596.36, admite hasta CUDA
13.2). La **imagen** contiene CUDA Toolkit 12.9.1 (`nvcc`, necesario porque PyCUDA compila
el kernel en tiempo de ejecución), Ubuntu 24.04, Python 3.12 y las dependencias fijadas en
`requirements.txt`. El runtime `nvidia` (NVIDIA Container Toolkit, en Docker Desktop con
WSL2) expone la GPU al contenedor con `--gpus all`. Base fijada:
`nvidia/cuda:12.9.1-devel-ubuntu24.04`; la RTX 3070 es *compute capability* 8.6 (`sm_86`).

```powershell
cd GuillenJ_SolanoA_Practica03
$env:COMMIT_PRACTICA03 = git -C .. rev-parse HEAD      # queda como etiqueta de la imagen
docker compose build                                    # o: docker compose --progress=plain build
docker compose up -d
docker compose exec convolucion nvidia-smi             # GPU visible dentro del contenedor
Invoke-RestMethod http://127.0.0.1:8080/api/salud       # 200 con datos de la GPU
docker compose down                                     # detener
```

Sin Compose:

```powershell
docker build --build-context practica02=../GuillenJ_SolanoA_Practica0 `
  --build-arg COMMIT_PRACTICA03=$(git -C .. rev-parse HEAD) -t convolucion-pycuda:p03 .
docker run --rm --gpus all -p 8080:8000 convolucion-pycuda:p03
```

El servidor es Gunicorn (1 proceso, 4 hilos, sin depurador ni recarga automática). Los
resultados temporales de las solicitudes van al volumen de Docker `salidas_servicio`; los
CSV y la evidencia, a `./resultados` (montado).

**Acceso desde otro equipo:** el puerto 8080 del anfitrión se publica en todas sus
interfaces: `http://IP_DEL_HOST:8080` (las IP quedan en `entorno_anfitrion_final.json`).
En Windows puede requerirse permitir el puerto en el firewall:
`New-NetFirewallRule -DisplayName "P03 convolucion" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow`.

## Instalación local (ejecución directa sin Docker)

Requisitos: Python 3.12, CUDA Toolkit 12.9, controlador NVIDIA compatible y Visual Studio
2022 con C++ (PyCUDA invoca `nvcc`, que necesita `cl.exe`).

```powershell
cd GuillenJ_SolanoA_Practica03
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest                     # pruebas sin GPU
cmd /c "..\GuillenJ_SolanoA_Practica0\scripts\entorno_vs.bat && .venv\Scripts\python.exe servidor.py"
```

## Validación y experimentos

```powershell
.\ejecutar_piloto.ps1                                     # imagen pequeña; valida todo
.\ejecutar_experimentos.ps1                               # corrida final (árbol limpio)
```

El ejecutor final se detiene si Git no está limpio, si las pruebas fallan o si el piloto
tiene alguna `FALLA`. Registra el commit de P02 (por defecto `1726b43…`; si ese commit está
disponible localmente, comprueba además que `../GuillenJ_SolanoA_Practica0/` no cambió) y el
de P03 (este último también dentro de la imagen), construye, mide, valida, prueba la imagen **sin GPU**, construye desde una **copia
limpia** del repositorio (`verificar_copia_limpia.ps1`) y comprueba con
`scripts/verificar_resultados_finales.py` que la matriz esté completa.

**Validación** (`resultados/pruebas/`):

| Archivo | Contenido |
|---|---|
| `prueba_manual_servicio.csv` | matriz 5×5 de P02 enviada al servicio; valores esperados |
| `bordes_cobertura.csv` | 1013×757 (766 841 px, 2996 bloques, 135 hilos sobrantes): imagen completa, bordes y último bloque contra referencia CPU float32, en las 5 máscaras |
| `validacion_directo_servicio.csv` | tres filtros: servicio vs PyCUDA directo con el mismo pipeline; error máx./medio antes del recorte |
| `entradas_invalidas.csv` | archivo no válido, mayor al límite, filtro desconocido, máscara no permitida |
| `aislamiento_solicitudes.csv` | dos solicitudes simultáneas con resultados propios |
| `cola_solicitudes.csv` | ráfagas de 4 solicitudes simultáneas (6000², media 21×21), repetidas hasta 5 rondas hasta que el límite produce HTTP 429; se registran todas las rondas |

**Experimentos** (calentamiento + 5 repeticiones; concurrencia: 5 rondas, una solicitud por
cliente), con 256 hilos por bloque y la misma GPU y datos:

- integración: PyCUDA directo en anfitrión, PyCUDA directo en contenedor y servicio (media
  9×9, 4000²); los tres usan `webapp/procesamiento.py`;
- resolución: 2000², 4000², 6000² (media 9×9);
- filtros y máscara: media 3/9/21, nitidez y laplaciano (4000²);
- concurrencia: 1 y 2 clientes simultáneos (media 9×9, 4000²).

**Columnas de `resultados/mediciones/*.csv`:** `id_solicitud, experimento, modo_ejecucion,
entorno, filtro, mascara, ancho, alto, sha256_entrada, hilos, bloques, repeticion, ronda,
concurrencia, t_recepcion_ms, t_decodificacion_ms, t_espera_ms, t_reserva_liberacion_ms,
t_h2d_ms, t_kernel_ms, t_d2h_ms, t_gpu_total_ms, t_codificacion_ms, t_servidor_ms,
t_cliente_ms, t_ronda_ms, rendimiento_rps, memoria_reservada_mb, memoria_gpu_usada_mb,
unidad, estado, observaciones`. `t_servidor_ms` es `procesamiento_total` en modo directo y
`servidor_total` en el servicio. `t_cliente_ms` comienza antes del envío multipart y termina
al descargar completo `resultado.png` (reloj del cliente). `rendimiento_rps` = solicitudes
exitosas / `t_ronda_ms`. Los relojes del cliente y del servidor nunca se restan entre sí.
La primera solicitud de cada proceso se registra como `arranque_frio` y se excluye de las
medianas. `resumen.csv` reporta mediana, Q1 y Q3 de cada columna.

## Resultados y evidencia

```text
resultados/
├── mediciones/  directo_anfitrion.csv, directo_contenedor.csv, servicio.csv, resumen.csv,
│                entorno_anfitrion_final.json, entorno_contenedor_final.json
├── pruebas/     validación funcional y numérica (tabla anterior)
├── graficas/    resolución, filtros, integración, distribución de tiempos, concurrencia
└── evidencia/   construccion_docker.txt, imagen_docker.json, salud_servicio.json,
                 contenedor_en_ejecucion.txt, nvidia_smi_contenedor.txt,
                 log_contenedor_final.txt, cliente_distinto.json, sin_gpu.json,
                 log_sin_gpu.txt, copia_limpia.json, construccion_copia_limpia.txt, visual/
```

Los entornos registran ubicación, CPU, RAM, GPU y memoria, SO, controlador, versión CUDA
del controlador y de `nvcc`, Docker y sus runtimes, Python y paquetes, IP, puertos, ID de la
imagen y commits. Ningún número se escribe a mano: todo sale de estos archivos.

## Despliegue

No se dispuso de instancia de nube con GPU; el servicio se despliega en un servidor local
con GPU NVIDIA (ver `entorno_anfitrion_final.json`), accesible en `http://IP_DEL_HOST:8080`
desde otros equipos de la red. La corrida final deja además evidencia de una solicitud desde
un contenedor cliente separado (`cliente_distinto.json`). La misma imagen puede desplegarse
en una instancia con GPU NVIDIA y NVIDIA Container Toolkit con `docker run --gpus all -p
8080:8000`; si se usa, detener la instancia después de la evaluación. La imagen Docker no se
adjunta al AVAC.

## Informe

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-documentos.txt
.\.venv\Scripts\python.exe -m scripts.generar_informe            # docs/informe/informe_practica03.docx
powershell -ExecutionPolicy Bypass -File scripts\exportar_pdf.ps1 # PDF con Microsoft Word
```

Todas las cifras del informe se leen de `resultados/`; las capturas de la demostración desde
otro equipo (Cloudflare Tunnel) están en `docs/informe/imagenes_otra_pc/`. El logotipo UPS
está en `informe/recursos/logo_ups.png`. Las firmas escaneadas (`informe/recursos/firmas/`)
no se versionan: si faltan, el informe deja el espacio para firmar a mano.
