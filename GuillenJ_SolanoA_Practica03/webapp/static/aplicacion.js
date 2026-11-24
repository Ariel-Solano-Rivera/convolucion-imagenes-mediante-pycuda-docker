const $ = (selector) => document.querySelector(selector);
const formulario = $("#formulario");
const entradaArchivo = $("#imagen");
const zona = $("#zona-archivo");
const vistaPrevia = $("#vista-previa");
const enviar = $("#enviar");
const textoBoton = $("#texto-boton");
const estado = $("#estado");
let urlOriginalLocal = null;

/* ---------- utilidades ---------- */
function formatearTiempo(valor) {
  if (valor === null || valor === undefined || Number.isNaN(Number(valor))) return "—";
  const ms = Number(valor);
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)} s`;
  if (ms >= 10) return `${ms.toFixed(1)} ms`;
  return `${ms.toFixed(2)} ms`;
}

function formatearBytes(bytes) {
  if (bytes >= 2 ** 20) return `${(bytes / 2 ** 20).toFixed(1)} MiB`;
  return `${(bytes / 1024).toFixed(0)} KiB`;
}

function mostrarEstado(texto, tipo = "") {
  estado.textContent = texto;
  estado.className = tipo;
}

function esperarImagen(imagen) {
  if (imagen.complete && imagen.naturalWidth > 0) return Promise.resolve();
  return new Promise((resolver, rechazar) => {
    imagen.addEventListener("load", resolver, { once: true });
    imagen.addEventListener("error", () => rechazar(new Error("No se pudo descargar la imagen final.")), { once: true });
  });
}

/* ---------- ficha del equipo ---------- */
function filaEspecificacion(nombre, valor) {
  const fila = document.createElement("div");
  const dt = document.createElement("dt");
  const dd = document.createElement("dd");
  dt.textContent = nombre;
  dd.textContent = valor ?? "—";
  fila.append(dt, dd);
  return fila;
}

function chip(nombre, valor) {
  const elemento = document.createElement("span");
  elemento.append(`${nombre} `);
  const negrita = document.createElement("b");
  negrita.textContent = valor;
  elemento.append(negrita);
  return elemento;
}

function insigniaGPU(disponible, texto) {
  const insignia = $("#insignia-gpu");
  insignia.className = `insignia ${disponible ? "insignia-ok" : "insignia-error"}`;
  insignia.replaceChildren(Object.assign(document.createElement("span"), { className: "punto" }), texto);
}

async function cargarEquipo() {
  try {
    const datos = await (await fetch("/api/equipo")).json();
    const s = datos.servidor;
    const g = datos.gpu;
    $("#eq-gpu").textContent = g ? g.gpu : "No disponible";
    $("#eq-chips").replaceChildren(...(g ? [
      chip("Memoria", `${(g.memoria_total_mb / 1024).toFixed(1)} GiB`),
      chip("Compute", g.compute_capability),
      chip("CUDA", `${g.cuda_controlador} / ${s.cuda_toolkit_nvcc}`),
      chip("Hilos/bloque", datos.limites.hilos_por_bloque),
    ] : [chip("Motivo", datos.error_gpu || "desconocido")]));
    $("#equipo").replaceChildren(
      filaEspecificacion("CPU", s.cpu),
      filaEspecificacion("Núcleos lógicos", s.nucleos_logicos),
      filaEspecificacion(s.en_contenedor ? "RAM del contenedor" : "RAM",
        s.ram_total_gib ? `${s.ram_total_gib} GiB${s.en_contenedor ? " (VM de Docker)" : ""}` : "—"),
      filaEspecificacion("Sistema", s.sistema),
      filaEspecificacion("Ejecución", s.en_contenedor ? `Contenedor Docker · ${s.hostname}` : `Directa · ${s.hostname}`),
      filaEspecificacion("Python · PyCUDA", `${s.python} · ${s.paquetes.pycuda}`),
      filaEspecificacion("Cola de GPU", `${datos.limites.solicitudes_gpu_simultaneas} solicitudes (ejecución + espera)`),
      filaEspecificacion("Commit", (s.commit_practica03 || "").slice(0, 12)),
    );
    insigniaGPU(Boolean(g), g ? `GPU lista · ${g.gpu.replace("NVIDIA GeForce ", "")}` : "GPU no disponible");
  } catch (error) {
    $("#eq-gpu").textContent = "No se pudo consultar el servicio";
    insigniaGPU(false, "Servicio no disponible");
  }
}

/* ---------- formulario ---------- */
function filtroSeleccionado() {
  return formulario.querySelector('input[name="filtro"]:checked').value;
}

function actualizarMascara() {
  const esMedia = filtroSeleccionado() === "media";
  formulario.querySelectorAll('input[name="mascara"]').forEach((opcion) => {
    opcion.disabled = !esMedia && opcion.value !== "3";
    if (!esMedia && opcion.value === "3") opcion.checked = true;
  });
  $("#nota-mascara").textContent = esMedia ? "" : "· nitidez y laplaciano usan 3 × 3";
}

function mostrarArchivo(archivo) {
  if (!archivo) return;
  $("#zona-texto").textContent = archivo.name;
  $("#zona-ayuda").textContent = `${formatearBytes(archivo.size)} · haz clic para cambiar`;
  zona.classList.add("con-archivo");
  if (urlOriginalLocal) URL.revokeObjectURL(urlOriginalLocal);
  urlOriginalLocal = URL.createObjectURL(archivo);
  vistaPrevia.hidden = false;
  vistaPrevia.onerror = () => { vistaPrevia.hidden = true; zona.classList.remove("con-archivo"); };
  vistaPrevia.src = urlOriginalLocal;
}

formulario.addEventListener("change", (evento) => {
  if (evento.target.name === "filtro") actualizarMascara();
  if (evento.target === entradaArchivo) mostrarArchivo(entradaArchivo.files[0]);
});
["dragenter", "dragover"].forEach((tipo) => zona.addEventListener(tipo, () => zona.classList.add("arrastrando")));
["dragleave", "drop"].forEach((tipo) => zona.addEventListener(tipo, () => zona.classList.remove("arrastrando")));

/* ---------- resultados ---------- */
function mostrarTiempos(tiempos, tiempoCliente) {
  $("#tiempo-cliente").textContent = formatearTiempo(tiempoCliente);
  $("#tiempo-servidor").textContent = formatearTiempo(tiempos.servidor_total);
  $("#tiempo-gpu").textContent = formatearTiempo(tiempos.gpu_total);
  $("#tiempo-espera").textContent = formatearTiempo(tiempos.espera_gpu);
  const fases = [
    ["Recepción", tiempos.recepcion, "Lectura del cuerpo multipart en el servidor"],
    ["Decodificación y preparación", tiempos.decodificacion_y_preparacion, "Validación, gris, recorte, redimensión y float32"],
    ["Espera en cola", tiempos.espera_gpu, "Hasta que el trabajador CUDA queda libre"],
    ["Reserva y liberación", tiempos.reserva_liberacion, "cuda.mem_alloc y free (fuera de GPU total)"],
    ["CPU → GPU", tiempos.cpu_a_gpu, "Entrada y máscara (eventos CUDA, memoria paginable)"],
    ["Kernel CUDA", tiempos.kernel, "Convolución en la GPU (eventos CUDA)"],
    ["GPU → CPU", tiempos.gpu_a_cpu, "Resultado (eventos CUDA)"],
    ["GPU total", tiempos.gpu_total, "CPU→GPU + kernel + GPU→CPU"],
    ["Codificación y escritura", tiempos.codificacion_y_escritura, "PNG de entrada y salida, y arreglo float32"],
    ["Servidor total", tiempos.servidor_total, "Desde la recepción hasta terminar la escritura"],
    ["Cliente total", tiempoCliente, "Envío, respuesta y descarga final (reloj del navegador)"],
  ];
  if (tiempos.inicio_frio !== null && tiempos.inicio_frio !== undefined) {
    fases.splice(2, 0, ["Arranque en frío", tiempos.inicio_frio, "Contexto CUDA y carga del kernel (solo la primera vez)"]);
  }
  $("#desglose-tiempos").replaceChildren(...fases.map(([fase, valor, alcance]) => {
    const fila = document.createElement("tr");
    [[fase, ""], [formatearTiempo(valor), "num"], [alcance, ""]].forEach(([texto, clase]) => {
      const celda = document.createElement("td");
      celda.textContent = texto;
      if (clase) celda.className = clase;
      fila.appendChild(celda);
    });
    return fila;
  }));
}

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const archivo = entradaArchivo.files[0];
  if (!archivo) {
    mostrarEstado("Selecciona una imagen antes de procesar.", "error");
    return;
  }
  const datos = new FormData(formulario);
  enviar.disabled = true;
  textoBoton.textContent = "Procesando en la GPU…";
  mostrarEstado("Enviando la imagen al servicio…");
  $("#salida").hidden = true;
  const inicioCliente = performance.now();
  try {
    const respuesta = await fetch("/api/convoluciones", { method: "POST", body: datos });
    const cuerpo = await respuesta.json();
    if (!respuesta.ok) {
      const detalle = cuerpo.codigo ? ` (HTTP ${respuesta.status} · ${cuerpo.codigo})` : ` (HTTP ${respuesta.status})`;
      throw new Error((cuerpo.error || "No se pudo procesar la imagen.") + detalle);
    }
    const imagenResultado = $("#resultado");
    imagenResultado.src = cuerpo.resultado_url;
    await esperarImagen(imagenResultado);
    const tiempoCliente = performance.now() - inicioCliente;

    // El navegador no muestra PGM/PPM: en ese caso se usa la entrada convertida por el servidor.
    const original = $("#original");
    original.onerror = () => { original.onerror = null; original.src = cuerpo.original_url; };
    original.src = urlOriginalLocal || cuerpo.original_url;
    $("#preparada").src = cuerpo.entrada_preparada_url || cuerpo.original_url;
    $("#descarga").href = cuerpo.resultado_url;

    const o = cuerpo.dimensiones_originales;
    const p = cuerpo.dimensiones;
    const nombreFiltro = `${cuerpo.filtro} ${cuerpo.mascara} × ${cuerpo.mascara}`;
    $("#titulo-resultado").textContent = `Resultado · ${nombreFiltro}`;
    $("#titulo-preparada").textContent = `Entrada preparada · ${p.ancho} × ${p.alto}`;
    $("#figura-preparada").hidden = !cuerpo.preparacion.aplicada;
    $("#preparacion").textContent = cuerpo.preparacion.aplicada
      ? `${o.ancho} × ${o.alto} → ${p.ancho} × ${p.alto}: recorte central${cuerpo.preparacion.redimensionada ? " y redimensión Lanczos" : ""} · solicitud ${cuerpo.id_solicitud.slice(0, 8)}`
      : `${p.ancho} × ${p.alto} píxeles · ${nombreFiltro} · solicitud ${cuerpo.id_solicitud.slice(0, 8)}`;

    mostrarTiempos(cuerpo.tiempos_ms, tiempoCliente);
    const gpu = cuerpo.gpu || {};
    $("#detalle-gpu").textContent =
      `${gpu.bloques} bloques × ${gpu.hilos_por_bloque} hilos · memoria reservada ${Number(gpu.memoria_reservada_mb).toFixed(1)} MiB` +
      (gpu.memoria_gpu_usada_mb != null ? ` · GPU en uso ${Number(gpu.memoria_gpu_usada_mb).toFixed(0)} / ${Number(gpu.memoria_gpu_total_mb).toFixed(0)} MiB` : "") +
      ` · transferencias ${gpu.transferencias}`;
    $("#salida").hidden = false;
    $("#salida").scrollIntoView({ behavior: "smooth", block: "start" });
    mostrarEstado(`Listo en ${formatearTiempo(tiempoCliente)}.`, "ok");
  } catch (error) {
    mostrarEstado(error instanceof TypeError
      ? "No se pudo conectar con el servicio. Verifica que el contenedor esté en ejecución."
      : error.message, "error");
  } finally {
    enviar.disabled = false;
    textoBoton.textContent = "Procesar en GPU";
  }
});

actualizarMascara();
cargarEquipo();
