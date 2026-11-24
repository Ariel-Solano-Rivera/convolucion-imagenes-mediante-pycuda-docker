from scripts.experimentos import configuraciones_servicio


def test_matriz_completa_contiene_experimentos_obligatorios(tmp_path):
    configuraciones = configuraciones_servicio(tmp_path, piloto=False)
    valores = {(filtro, k, ruta.name) for _experimento, filtro, k, ruta in configuraciones}
    assert ("media", 9, "base_2000.pgm") in valores
    assert ("media", 9, "base_4000.pgm") in valores
    assert ("media", 9, "base_6000.pgm") in valores
    assert ("media", 3, "base_4000.pgm") in valores
    assert ("media", 21, "base_4000.pgm") in valores
    assert ("nitidez", 3, "base_4000.pgm") in valores
    assert ("laplaciano", 3, "base_4000.pgm") in valores

