# Se construye con BuildKit y un contexto adicional llamado practica02
# (../GuillenJ_SolanoA_Practica0: kernel propio, código PyCUDA y datos de la práctica 02).
#
# Compatibilidad: la imagen aporta CUDA Toolkit 12.9.1 (nvcc, necesario porque PyCUDA
# compila el kernel con SourceModule en tiempo de ejecución), Ubuntu 24.04 y Python 3.12.
# El controlador NVIDIA NO va en la imagen: lo expone el anfitrión mediante NVIDIA
# Container Toolkit (--gpus all). Requiere un controlador que admita CUDA >= 12.9.
FROM nvidia/cuda:12.9.1-devel-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PRACTICA02_ROOT=/opt/practica02

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-dev build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt
COPY . .
# El contexto nombrado evita copiar o modificar la práctica 02 dentro de esta carpeta.
COPY --from=practica02 src /opt/practica02/src
COPY --from=practica02 datos /opt/practica02/datos

# El commit se declara al final para no invalidar la caché de apt/pip en cada commit.
ARG COMMIT_PRACTICA03=no_declarado
LABEL org.opencontainers.image.title="convolucion-pycuda" \
      org.opencontainers.image.description="Practica 03: servicio web de convolucion con PyCUDA" \
      org.opencontainers.image.revision="${COMMIT_PRACTICA03}"
ENV COMMIT_PRACTICA03=${COMMIT_PRACTICA03}

EXPOSE 8000
# Un proceso evita contextos CUDA duplicados. Cuatro hilos reciben clientes;
# el trabajador CUDA interno serializa el acceso real a la GPU. Sin depurador ni recarga.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--timeout", "300", "--access-logfile", "-", "--error-logfile", "-", "servidor:app"]
