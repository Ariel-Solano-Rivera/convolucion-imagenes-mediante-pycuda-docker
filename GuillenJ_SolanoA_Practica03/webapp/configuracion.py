"""Límites y rutas configurables del servicio."""
import os
from dataclasses import dataclass
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
PRACTICA02_PREDETERMINADA = RAIZ.parent / "GuillenJ_SolanoA_Practica0"


@dataclass(frozen=True)
class Configuracion:
    directorio_resultados: Path
    practica02: Path
    # base_6000.pgm ocupa algo más de 36 MB; 64 MiB permite el experimento
    # obligatorio y sigue siendo un límite explícito y razonable para la RTX 3070.
    max_bytes_archivo: int = 64 * 1024 * 1024
    # Permite la imagen fuente de 12 500² y evita decodificaciones sin límite.
    max_pixeles_entrada: int = 170_000_000
    # El kernel procesa como máximo 6000², igual que en las prácticas anteriores.
    max_pixeles: int = 36_000_000
    hilos_por_bloque: int = 256
    limite_trabajos_gpu: int = 2
    retencion_resultados_segundos: int = 24 * 60 * 60

    @classmethod
    def desde_entorno(cls):
        return cls(
            directorio_resultados=Path(os.environ.get(
                "RESULTADOS_PRACTICA03", RAIZ / "runtime" / "resultados")),
            practica02=Path(os.environ.get("PRACTICA02_ROOT", PRACTICA02_PREDETERMINADA)),
            max_bytes_archivo=int(os.environ.get("MAX_BYTES_ARCHIVO", 64 * 1024 * 1024)),
            max_pixeles_entrada=int(os.environ.get("MAX_PIXELES_ENTRADA", 170_000_000)),
            max_pixeles=int(os.environ.get("MAX_PIXELES", 36_000_000)),
            hilos_por_bloque=int(os.environ.get("HILOS_POR_BLOQUE", 256)),
            limite_trabajos_gpu=int(os.environ.get("LIMITE_TRABAJOS_GPU", 2)),
            retencion_resultados_segundos=int(os.environ.get("RETENCION_RESULTADOS_SEGUNDOS", 24 * 60 * 60)),
        )

    def como_dict(self):
        return {
            "DIRECTORIO_RESULTADOS": self.directorio_resultados,
            "PRACTICA02_ROOT": self.practica02,
            "MAX_CONTENT_LENGTH": self.max_bytes_archivo,
            "MAX_PIXELES_ENTRADA": self.max_pixeles_entrada,
            "MAX_PIXELES": self.max_pixeles,
            "HILOS_POR_BLOQUE": self.hilos_por_bloque,
            "LIMITE_TRABAJOS_GPU": self.limite_trabajos_gpu,
            "RETENCION_RESULTADOS_SEGUNDOS": self.retencion_resultados_segundos,
        }

