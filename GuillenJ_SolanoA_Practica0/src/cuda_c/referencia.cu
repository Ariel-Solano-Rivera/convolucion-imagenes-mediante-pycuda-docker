// Extension de P02 sobre el codigo de P01: exporta salidas float32 crudas (antes del
// recorte) de C++ secuencial y CUDA C, y mide C++/CUDA C en imagenes nuevas.
// No modifica P01: se compila enlazando sus fuentes por ruta relativa (compilar_referencia.bat)
// y usa sus funciones tal cual: leerPGM, crearMascara, convolucionCPU, ejecutarCPU,
// ejecutarGPU, ejecutarFiltroCPU y ejecutarFiltroGPU.
//
// Modos:
//   mascaras  <carpeta>
//   pgm       <imagen.pgm> <filtro> <k> <hilos> <salida_cpp.bin|-> <salida_cuda.bin|->
//   crudo     <entrada.bin> <ancho> <alto> <mascara.bin> <k> <hilos> <salida_cpp.bin> <salida_cuda.bin>
//   medir     <imagen.pgm> <filtro> <k> <hilos> <medir_cpu 0|1> <mediciones.csv>
#include "configuracion.h"
#include "filtros.cuh"
#include "imagenes.h"
#include "cuda_c/filtros_paralelos.cuh"
#include "secuencial_c/filtros_secuenciales.h"

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cuda_runtime.h>
#include <string>
#include <vector>

namespace {

void guardarBin(const char* ruta, const float* datos, size_t n) {
    if (std::strcmp(ruta, "-") == 0) return;
    FILE* archivo = std::fopen(ruta, "wb");
    if (!archivo) { std::fprintf(stderr, "No se pudo escribir %s\n", ruta); std::exit(1); }
    std::fwrite(datos, sizeof(float), n, archivo);
    std::fclose(archivo);
}

std::vector<float> leerBin(const char* ruta, size_t n) {
    std::vector<float> datos(n);
    FILE* archivo = std::fopen(ruta, "rb");
    if (!archivo || std::fread(datos.data(), sizeof(float), n, archivo) != n) {
        std::fprintf(stderr, "No se pudo leer %s\n", ruta);
        std::exit(1);
    }
    std::fclose(archivo);
    return datos;
}

int filtroDeNombre(const char* nombre) {
    for (int f = MEDIA; f <= LAPLACIANO; f++)
        if (std::strcmp(nombre, NOMBRE_FILTRO[f]) == 0) return f;
    std::fprintf(stderr, "Filtro desconocido: %s\n", nombre);
    std::exit(1);
}

// Una ejecucion de convolucionCPU y una de ejecutarGPU (como calcularAmbas de P01).
void calcularYExportar(const float* entrada, int ancho, int alto, const float* mascara,
                       int k, int hilos, const char* rutaCpp, const char* rutaCuda) {
    size_t n = (size_t)ancho * alto;
    std::vector<float> cpu(n), gpu(n);
    if (std::strcmp(rutaCpp, "-") != 0) {
        convolucionCPU(entrada, cpu.data(), mascara, ancho, alto, k);
        guardarBin(rutaCpp, cpu.data(), n);
    }
    if (std::strcmp(rutaCuda, "-") != 0) {
        float *dEntrada, *dSalida, *dMascara;
        cudaMalloc(&dEntrada, n * sizeof(float));
        cudaMalloc(&dSalida, n * sizeof(float));
        cudaMalloc(&dMascara, k * k * sizeof(float));
        ejecutarGPU(entrada, gpu.data(), mascara, dEntrada, dSalida, dMascara,
                    ancho, alto, k, hilos);
        cudaFree(dEntrada);
        cudaFree(dSalida);
        cudaFree(dMascara);
        cudaError_t error = cudaGetLastError();
        if (error != cudaSuccess) {
            std::fprintf(stderr, "CUDA: %s\n", cudaGetErrorString(error));
            std::exit(1);
        }
        guardarBin(rutaCuda, gpu.data(), n);
    }
}

// Mismo bucle que ejecutar() de P01 (experimentos.cu:49-101), escribiendo el esquema de P02.
void medir(const char* rutaImagen, int filtro, int k, int hilos, bool medirCPU,
           const char* rutaCsv) {
    int ancho, alto;
    float* datos = leerPGM(rutaImagen, &ancho, &alto);
    int n = ancho * alto;
    int bloques = (n + hilos - 1) / hilos;
    std::vector<float> cpu(n), gpu(n);
    FILE* tiempos = std::fopen(rutaCsv, "a");
    if (!tiempos) { std::fprintf(stderr, "No se pudo abrir %s\n", rutaCsv); std::exit(1); }

    std::printf("[%s %dx%d] imagen %dx%d, %d hilos, %d bloques\n", NOMBRE_FILTRO[filtro],
                k, k, ancho, alto, hilos, bloques);

    if (medirCPU) {
        // Calentamiento CPU: esta ejecucion no se guarda.
        ejecutarFiltroCPU(filtro, datos, cpu.data(), ancho, alto, k);
        for (int r = 1; r <= REPETICIONES; r++) {
            double t = ejecutarFiltroCPU(filtro, datos, cpu.data(), ancho, alto, k);
            std::fprintf(tiempos,
                         "cpp_secuencial,%s,%d,%d,%d,NA,NA,%d,NA,NA,NA,%.4f,ms,"
                         "completada,NA,nuevo\n",
                         NOMBRE_FILTRO[filtro], k, ancho, alto, r, t);
            std::fflush(tiempos);
        }
    }

    float *dEntrada, *dSalida, *dMascara;
    cudaMalloc(&dEntrada, n * sizeof(float));
    cudaMalloc(&dSalida, n * sizeof(float));
    cudaMalloc(&dMascara, k * k * sizeof(float));

    // Calentamiento GPU durante dos segundos, sin guardar sus tiempos.
    auto inicio = std::chrono::steady_clock::now();
    while (std::chrono::duration<double>(std::chrono::steady_clock::now() - inicio).count() <
           SEGUNDOS_CALENTAMIENTO_GPU) {
        ejecutarFiltroGPU(filtro, datos, gpu.data(), dEntrada, dSalida, dMascara, ancho,
                          alto, k, hilos);
    }

    for (int r = 1; r <= REPETICIONES; r++) {
        TiemposGPU t = ejecutarFiltroGPU(filtro, datos, gpu.data(), dEntrada, dSalida,
                                         dMascara, ancho, alto, k, hilos);
        std::fprintf(tiempos,
                     "cuda_c,%s,%d,%d,%d,%d,%d,%d,%.4f,%.4f,%.4f,%.4f,ms,completada,NA,nuevo\n",
                     NOMBRE_FILTRO[filtro], k, ancho, alto, hilos, bloques, r, t.h2d,
                     t.kernel, t.d2h, t.total);
        std::fflush(tiempos);
    }

    cudaFree(dEntrada);
    cudaFree(dSalida);
    cudaFree(dMascara);
    std::fclose(tiempos);
    std::free(datos);
}

int uso() {
    std::fprintf(stderr, "Uso: referencia mascaras|pgm|crudo|medir ... "
                         "(ver cabecera de referencia.cu)\n");
    return 1;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) return uso();
    std::string modo = argv[1];

    if (modo == "mascaras" && argc == 3) {
        std::string carpeta = argv[2];
        for (int k : {3, 9, 21}) {
            auto m = crearMascara(MEDIA, k);
            guardarBin((carpeta + "/mascara_media" + std::to_string(k) + ".bin").c_str(),
                       m.data(), m.size());
        }
        auto nit = crearMascara(NITIDEZ, 3);
        auto lap = crearMascara(LAPLACIANO, 3);
        guardarBin((carpeta + "/mascara_nitidez3.bin").c_str(), nit.data(), nit.size());
        guardarBin((carpeta + "/mascara_laplaciano3.bin").c_str(), lap.data(), lap.size());
        return 0;
    }
    if (modo == "pgm" && argc == 8) {
        int ancho, alto, k = std::atoi(argv[4]);
        float* datos = leerPGM(argv[2], &ancho, &alto);
        auto mascara = crearMascara(filtroDeNombre(argv[3]), k);
        calcularYExportar(datos, ancho, alto, mascara.data(), k, std::atoi(argv[5]),
                          argv[6], argv[7]);
        std::free(datos);
        return 0;
    }
    if (modo == "crudo" && argc == 10) {
        int ancho = std::atoi(argv[3]), alto = std::atoi(argv[4]), k = std::atoi(argv[6]);
        auto entrada = leerBin(argv[2], (size_t)ancho * alto);
        auto mascara = leerBin(argv[5], (size_t)k * k);
        calcularYExportar(entrada.data(), ancho, alto, mascara.data(), k, std::atoi(argv[7]),
                          argv[8], argv[9]);
        return 0;
    }
    if (modo == "medir" && argc == 8) {
        medir(argv[2], filtroDeNombre(argv[3]), std::atoi(argv[4]), std::atoi(argv[5]),
              std::atoi(argv[6]) != 0, argv[7]);
        return 0;
    }
    return uso();
}
