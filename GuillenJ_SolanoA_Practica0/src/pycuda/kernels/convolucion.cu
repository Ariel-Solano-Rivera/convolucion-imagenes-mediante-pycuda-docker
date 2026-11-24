// Kernel CUDA de P01 (convolucionGPU, src/filtros.cu:39-59), copiado sin cambios de logica.
// Se compila desde Python con SourceModule (-O3, arch=sm_86), que lo envuelve en extern "C".
//
// Distribucion: bloques e hilos solo en X; cada hilo calcula un pixel de salida.
//   id = blockIdx.x * blockDim.x + threadIdx.x   indice global del hilo = indice del pixel
//   if (id >= n) return;   el ultimo bloque puede tener hilos de sobra (n no multiplo de
//                          hilos): esos hilos salen sin leer ni escribir fuera de la imagen.
//   y = id / ancho, x = id % ancho   fila y columna del pixel en la imagen guardada por filas.
// Los vecinos se leen de memoria global; los que caen fuera de la imagen se omiten
// (extension con ceros). Entrada y salida son arreglos distintos.
// Tipos: entrada, salida y mascara son float (np.float32); ancho, alto y k son int (np.int32).

// Kernel CUDA: un hilo calcula un pixel de la imagen.
__global__ void convolucionGPU(const float* entrada, float* salida,
                               const float* mascara, int ancho, int alto,
                               int k) {
    int id = blockIdx.x * blockDim.x + threadIdx.x;
    int n = ancho * alto;
    if (id >= n) return;

    int y = id / ancho, x = id % ancho, radio = k / 2;
    float suma = 0;
    for (int j = -radio; j <= radio; j++) {
        for (int i = -radio; i <= radio; i++) {
            int yy = y + j, xx = x + i;
            if (yy >= 0 && yy < alto && xx >= 0 && xx < ancho) {
                suma += entrada[yy * ancho + xx] *
                        mascara[(j + radio) * k + i + radio];
            }
        }
    }
    salida[id] = suma;
}
