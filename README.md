# Servicio web de convolución de imágenes con Docker y PyCUDA

## Resumen

Servicio web que aplica filtros de convolución a imágenes usando la GPU con PyCUDA. Se sube
una imagen, se elige un filtro y se obtiene la imagen procesada. Todo corre dentro de un
contenedor Docker.

## Cómo ejecutar

Requisitos: GPU NVIDIA, Docker Desktop (con WSL2) y Git.

```powershell
git clone https://github.com/Ariel-Solano-Rivera/convolucion-imagenes-mediante-pycuda-docker.git
cd convolucion-imagenes-mediante-pycuda-docker\GuillenJ_SolanoA_Practica03
docker compose build
docker compose up -d
```

Abrir **http://127.0.0.1:8080** en el navegador.

Para detenerlo:

```powershell
docker compose down
```

Más opciones de ejecución en [GuillenJ_SolanoA_Practica03/README.md](GuillenJ_SolanoA_Practica03/README.md).
