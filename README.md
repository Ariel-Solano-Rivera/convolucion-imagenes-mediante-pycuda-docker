# Práctica 03 · Servicio web de convolución de imágenes con Docker y PyCUDA

Computación Paralela · Universidad Politécnica Salesiana · Juan Alberto Guillén y Ariel Solano.

Servicio web en Python (Flask + Gunicorn) que carga una imagen, aplica un filtro de
convolución (media 3×3, 9×9 o 21×21, nitidez 3×3 o laplaciano 3×3) en una GPU NVIDIA con el
**kernel CUDA propio de la práctica 02** ejecutado mediante PyCUDA, y devuelve el resultado.
Todo se ejecuta dentro de un contenedor Docker con acceso a la GPU del anfitrión.

```text
navegador → Flask/Gunicorn → cola acotada → trabajador PyCUDA → GPU → resultado → navegador
```

## Contenido del repositorio

| Carpeta | Contenido |
|---|---|
| [`GuillenJ_SolanoA_Practica03/`](GuillenJ_SolanoA_Practica03/) | **Práctica 03**: aplicación web, Dockerfile, `compose.yaml`, pruebas, scripts de validación y experimentos, CSV, gráficas y evidencia. Ver su [README](GuillenJ_SolanoA_Practica03/README.md). |
| [`GuillenJ_SolanoA_Practica0/`](GuillenJ_SolanoA_Practica0/) | Prácticas 01 y 02 (C++, CUDA C, Python secuencial y PyCUDA): kernel, código PyCUDA e imágenes de entrada que reutiliza la práctica 03. Se incluye **sin cambios** como versión ejecutable de referencia. |
| [`docs/informe/`](docs/informe/) | Informe de la práctica 03 (`informe_practica03.pdf` y `.docx`) y capturas de la demostración desde otro equipo. |

El informe y la presentación de la práctica 02 que menciona el README de
`GuillenJ_SolanoA_Practica0/` se entregaron con la práctica 02 en su propio repositorio y no
forman parte de este.

## Trazabilidad

| Elemento | Valor |
|---|---|
| Repositorio de la práctica 03 | https://github.com/Ariel-Solano-Rivera/convolucion-imagenes-mediante-pycuda-docker |
| Commit de la práctica 03 medido | el registrado en `GuillenJ_SolanoA_Practica03/resultados/mediciones/entorno_*_final.json` (también en la etiqueta `org.opencontainers.image.revision` de la imagen) |
| Repositorio de la práctica 02 | https://github.com/JuanGuillenA/procesamiento-imagenes-pycuda |
| Commit de origen de la práctica 02 | `1726b43d8dc8078bee7b8e679c29b0049e0f707f` |

## Datos

Las imágenes de entrada son las mismas de las prácticas 01 y 02 y están versionadas en
`GuillenJ_SolanoA_Practica0/datos/` (`base_2000.pgm`, `base_4000.pgm`, `base_6000.pgm`,
`no_multiplo_1013x757.pgm` y `base_250.pgm` para el piloto). Sus SHA-256 están en
`GuillenJ_SolanoA_Practica0/datos/hashes_p01.json` y en la columna `sha256_entrada` de cada
medición.

## Inicio rápido

Requisitos: GPU NVIDIA con controlador compatible con CUDA 12.9, Docker con NVIDIA Container
Toolkit (en Windows, Docker Desktop con WSL2).

```powershell
git clone https://github.com/Ariel-Solano-Rivera/convolucion-imagenes-mediante-pycuda-docker.git
cd convolucion-imagenes-mediante-pycuda-docker\GuillenJ_SolanoA_Practica03
$env:COMMIT_PRACTICA03 = git -C .. rev-parse HEAD
docker compose build
docker compose up -d
docker compose exec convolucion nvidia-smi          # la GPU es visible en el contenedor
Invoke-RestMethod http://127.0.0.1:8080/api/salud    # 200 con los datos de la GPU
# Interfaz web: http://127.0.0.1:8080
curl.exe -s -F "imagen=@..\GuillenJ_SolanoA_Practica0\datos\base_2000.pgm" `
  -F filtro=media -F mascara=9 http://127.0.0.1:8080/api/convoluciones
docker compose down
```

El contrato HTTP completo, la arquitectura, la validación, los experimentos y la generación
del informe están en el [README de la práctica 03](GuillenJ_SolanoA_Practica03/README.md).
