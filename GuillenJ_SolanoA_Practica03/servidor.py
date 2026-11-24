"""Punto de entrada del servicio de convolución de la práctica 03."""
from webapp import crear_aplicacion

app = crear_aplicacion()


if __name__ == "__main__":
    # Solo para pruebas locales. En el contenedor se usa Gunicorn: 1 proceso, 4 hilos HTTP
    # y un único trabajador CUDA interno (ver webapp/procesador_gpu.py).
    app.run(host="0.0.0.0", port=8000, debug=False, threaded=False)

