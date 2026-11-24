# Evidencia que debe conservarse

- salida de construcción de Docker;
- `nvidia-smi` dentro del contenedor;
- contenedor saludable y puerto publicado;
- solicitud exitosa que genere UUID, PNG y tiempos PyCUDA;
- respuestas 400, 413 y, si se fuerza el límite de cola, 429;
- acceso desde un segundo cliente o evidencia del despliegue en nube;
- identificación final de imagen Docker y commits exactos;
- apagado de recursos de pago, si se usaron.

La carpeta `visual/` se genera automáticamente durante `scripts.validar_servicio`.
