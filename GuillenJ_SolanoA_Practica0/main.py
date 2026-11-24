"""Inicio del programa: pruebas, validacion y experimentos (equivale a main.cu de P01).

Uso (desde GuillenJ_SolanoA_Practica02, con cl.exe en el PATH):
    python main.py validar      prueba manual, no multiplo y validacion numerica
"""
import sys

from src.pycuda.contexto_cuda import cerrar_cuda, inicializar_cuda
from src.python.comun.imagenes import verificar_datos_p01


def validar():
    from src.python.comun.experimentos import (prueba_manual,
                                                         validacion_completa)
    manual = prueba_manual()
    ok_manual = sum(f["resultado"] == "OK" for f in manual)
    print(f"prueba_manual_python_pycuda.csv: {ok_manual}/{len(manual)} OK")
    filas = validacion_completa()
    fallas = [f for f in filas if f["resultado"] != "OK"]
    print(f"validacion_python_pycuda.csv: {len(filas) - len(fallas)}/{len(filas)} OK")
    for fila in fallas:
        print("  FALLA:", fila)
    return 1 if fallas or ok_manual != len(manual) else 0


def main():
    orden = sys.argv[1] if len(sys.argv) > 1 else "validar"
    print(f"Datos de P01 verificados por SHA-256: {verificar_datos_p01()} archivos")
    entorno = inicializar_cuda()  # contexto y kernel una sola vez por proceso
    entorno.registrar()
    try:
        if orden == "validar":
            return validar()
        print(f"Orden desconocida: {orden}")
        return 1
    finally:
        cerrar_cuda()


if __name__ == "__main__":
    sys.exit(main())
