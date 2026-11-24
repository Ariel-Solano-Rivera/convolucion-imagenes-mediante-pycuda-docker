# Cumplimiento de la guía de práctica 03 (parte de código)

Un requisito que depende de una ejecución real solo se da por cumplido cuando existe su
CSV o evidencia generados por `ejecutar_experimentos.ps1` sobre un commit limpio.

| Requisito de la guía | Dónde se implementa | Evidencia que genera |
|---|---|---|
| Identificar repositorio y commit de P02; versión ejecutable directa | README; `-CommitPractica02`; `../GuillenJ_SolanoA_Practica0` | `entorno_*_final.json` |
| Mismos kernels, máscaras, float32, ceros, un píxel por hilo en X | kernel y PyCUDA de P02 importados sin copiar; `webapp/filtros.py` | `tests/test_filtros.py`, `bordes_cobertura.csv` |
| Imágenes 2000², 4000², 6000² con hash | `scripts/experimentos.py` (`sha256_entrada`) | `mediciones/*.csv` |
| Cargar imagen, filtro, máscara de media; ver original y resultado; descargar | `webapp/static/` | interfaz en `/` |
| Servicio HTTP documentado (ruta, campos, respuesta, errores) | `webapp/api.py`; README | `tests/test_api.py` |
| Tiempos con unidades y alcance en la interfaz | `aplicacion.js` (desglose por fase) | — |
| Evitar duplicados accidentales y comunicar errores | botón deshabilitado; mensaje con HTTP y código | — |
| Validar formato real, dimensiones, tamaño y parámetros | `webapp/imagenes.py`, `filtros.py`, `MAX_CONTENT_LENGTH` | `entradas_invalidas.csv` |
| UUID, nombres únicos, limpieza, aislamiento | `webapp/almacenamiento.py` | `aislamiento_solicitudes.csv` |
| Separar HTTP de la convolución (mismo procesamiento directo y servicio) | `webapp/procesamiento.py` usado por API, experimentos y validación | `validacion_directo_servicio.csv` |
| Contexto, kernel, reserva/liberación, transferencias, sincronización | `webapp/procesador_gpu.py` (docstring) y README | `inicio_frio`, `t_reserva_liberacion_ms` |
| Inicialización registrada por separado | fila `arranque_frio` | `mediciones/*.csv` |
| Fallos de carga, falta de memoria, errores del kernel | códigos 503/500 diferenciados; reinicio de contexto | `tests/test_errores_y_pipeline.py` |
| Sin GPU → diagnóstico claro, sin CPU sustituta | `/api/salud` 503; `scripts/probar_sin_gpu.py` | `evidencia/sin_gpu.json` |
| Dockerfile con versiones fijas y compatibilidad | `Dockerfile`, `requirements.txt` | `construccion_docker.txt`, `imagen_docker.json` |
| Controlador del anfitrión vs CUDA de la imagen; runtime GPU | README; `registrar_entorno.py` | `entorno_*_final.json`, `nvidia_smi_contenedor.txt` |
| Servidor adecuado, sin depurador ni recarga | Gunicorn 1×4 | `log_contenedor_final.txt` |
| Construcción desde copia limpia; imagen, base y commit registrados | `verificar_copia_limpia.ps1`; etiqueta `org.opencontainers.image.revision` | `copia_limpia.json` |
| Entorno: ubicación, CPU, RAM, GPU, SO, driver, Docker, Python, PyCUDA, CUDA, puertos | `scripts/registrar_entorno.py` | `entorno_*_final.json` |
| Contenedor en ejecución y solicitud real con PyCUDA | ejecutor final | `contenedor_en_ejecucion.txt`, `salud_servicio.json`, `servicio.csv` |
| Cliente distinto | `scripts/probar_cliente_distinto.py` | `cliente_distinto.json` |
| Matriz pequeña, no múltiplo, bordes y cobertura | `scripts/validar_servicio.py` | `prueba_manual_servicio.csv`, `bordes_cobertura.csv` |
| Equivalencia directo–servicio, error máx./medio antes del recorte | `validar_servicio.py` (`resultado.npy`) | `validacion_directo_servicio.csv` |
| Resultado visual (original, 3 filtros, recortes) | `validar_servicio.py` | `evidencia/visual/` |
| Cola o rechazo al alcanzar el límite | semáforo de 2 cupos | `cola_solicitudes.csv` |
| Experimentos: integración, resolución, filtros/máscara, concurrencia | `scripts/experimentos.py` | `directo_*.csv`, `servicio.csv` |
| Calentamiento, ≥5 repeticiones, 5 rondas, mediana y variabilidad | `experimentos.py`, `resumir_resultados.py` (mediana, Q1, Q3) | `resumen.csv` |
| H2D, kernel, D2H con eventos; memoria paginable declarada | P02 + `procesador_gpu.py` | columnas `t_h2d/kernel/d2h_ms` |
| Servidor por fases (decodificación, transferencias, kernel, salida, espera) | `procesamiento.py` | columnas `t_*_ms` |
| Cliente hasta la imagen final; rendimiento por ronda | `scripts/util_http.py`, `experimentos.py` | `t_cliente_ms`, `t_ronda_ms`, `rendimiento_rps` |
| Memoria según resolución, máscara y concurrencia | `memoria_reservada_mb`, `memoria_gpu_usada_mb` | `mediciones/*.csv` |
| Gráficas | `scripts/generar_graficas.py` | `resultados/graficas/` |
| Configuraciones no completadas registradas, sin estimaciones | `estado`, `observaciones` | `mediciones/*.csv` |

## Entrega

| Requisito | Dónde |
|---|---|
| Informe PDF (relación con P02, arquitectura, entorno, validación, tablas, gráficas, análisis, conclusiones, limitaciones, contribuciones y firmas) | `../docs/informe/informe_practica03.pdf`, generado con `scripts/generar_informe.py` |
| Demostración desde otro equipo (Cloudflare Tunnel) | capturas en `../docs/informe/imagenes_otra_pc/` |
| Repositorio, commit de P03 y commit de origen de P02 | `README.md` de la raíz y `entorno_*_final.json` |
