param(
    [string]$Python = ".\.venv\Scripts\python.exe",
    # Commit de origen de la práctica 02 (repositorio de la práctica 02). Su carpeta
    # GuillenJ_SolanoA_Practica0/ se incluye sin cambios en este repositorio.
    [string]$CommitPractica02 = "1726b43d8dc8078bee7b8e679c29b0049e0f707f",
    [switch]$OmitirCopiaLimpia
)

$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $Raiz
try {
    if (-not (Test-Path -LiteralPath $Python)) {
        throw "No existe $Python. Cree .venv e instale requirements.txt."
    }
    $EstadoGit = @(git -C .. status --porcelain)
    if ($LASTEXITCODE -ne 0) { throw "No se pudo consultar el repositorio Git." }
    if ($EstadoGit.Count -gt 0) {
        throw "El árbol Git debe estar limpio antes de medir. Revise 'git status --short'."
    }
    if ($CommitPractica02 -notmatch '^[0-9a-f]{40}$') {
        throw "CommitPractica02 debe ser el hash completo (40 caracteres hexadecimales)."
    }
    # El commit de P02 vive en el repositorio de la práctica 02. Si también está disponible
    # localmente, se comprueba que la carpeta de P02 no cambió desde ese commit.
    cmd /d /c "git -C .. cat-file -e $CommitPractica02 2>nul"
    if ($LASTEXITCODE -eq 0) {
        git -C .. diff --quiet $CommitPractica02 HEAD -- GuillenJ_SolanoA_Practica0
        if ($LASTEXITCODE -ne 0) { throw "GuillenJ_SolanoA_Practica0/ difiere del commit $CommitPractica02." }
    }
    $CommitPractica03 = git -C .. rev-parse HEAD
    if ($LASTEXITCODE -ne 0 -or -not $CommitPractica03) { throw "No se pudo registrar el commit de práctica 03." }
    # Compose lo pasa como build-arg: queda en la etiqueta y en el entorno de la imagen.
    $env:COMMIT_PRACTICA03 = $CommitPractica03
    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Las pruebas automatizadas fallaron." }
    if (-not (Test-Path -LiteralPath "resultados/pruebas/validacion_directo_servicio.csv")) {
        throw "Ejecute primero .\ejecutar_piloto.ps1 y revise que la validación no tenga FALLA."
    }
    $FilasPrueba = Get-ChildItem -LiteralPath "resultados/pruebas" -Filter "*.csv" |
        ForEach-Object { Import-Csv -LiteralPath $_.FullName }
    $Fallas = @($FilasPrueba | Where-Object {
        $_.resultado -eq "FALLA" -or $_.aislamiento -eq "FALLA"
    })
    if ($Fallas.Count -gt 0) {
        throw "Existen $($Fallas.Count) fallas en resultados/pruebas; no se ejecutarán mediciones finales."
    }
    New-Item -ItemType Directory -Force resultados/evidencia | Out-Null

    # Evidencia de construcción (cmd evita que PowerShell 5.1 trate stderr como excepción).
    cmd /d /c "docker compose --progress=plain build > resultados\evidencia\construccion_docker.txt 2>&1"
    if ($LASTEXITCODE -ne 0) { throw "Falló la construcción de la imagen Docker (ver construccion_docker.txt)." }
    docker image inspect convolucion-pycuda:p03 | Set-Content -Encoding utf8 -LiteralPath resultados/evidencia/imagen_docker.json
    & $Python -m scripts.registrar_entorno --entorno anfitrion_final `
        --commit-practica02 $CommitPractica02 --commit-practica03 $CommitPractica03 `
        --arbol-limpio-verificado
    if ($LASTEXITCODE -ne 0) { throw "No se pudo registrar el entorno anfitrion." }
    docker compose up --detach
    $Listo = $false
    for ($Intento = 1; $Intento -le 24; $Intento++) {
        try {
            $Salud = Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/salud" -TimeoutSec 5
            $Listo = $true
            break
        } catch { Start-Sleep -Seconds 5 }
    }
    if (-not $Listo) { throw "El servicio no respondió (o /api/salud informó que no hay GPU)." }
    $Salud | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 -LiteralPath resultados/evidencia/salud_servicio.json
    cmd /d /c "docker compose ps > resultados\evidencia\contenedor_en_ejecucion.txt 2>&1"
    cmd /d /c "docker compose exec -T convolucion nvidia-smi > resultados\evidencia\nvidia_smi_contenedor.txt 2>&1"
    if ($LASTEXITCODE -ne 0) { throw "La GPU no esta visible dentro del contenedor." }
    docker compose exec -T convolucion python3 -m scripts.registrar_entorno `
        --entorno contenedor_final --commit-practica02 $CommitPractica02 `
        --commit-practica03 $CommitPractica03 --arbol-limpio-verificado
    if ($LASTEXITCODE -ne 0) { throw "No se pudo registrar el entorno del contenedor." }

    $ComandoDirecto = "call ..\GuillenJ_SolanoA_Practica0\scripts\entorno_vs.bat && $Python -m scripts.experimentos directo --entorno anfitrion --salida resultados\mediciones\directo_anfitrion.csv"
    cmd /d /s /c $ComandoDirecto
    if ($LASTEXITCODE -ne 0) { throw "Falló PyCUDA directo en el anfitrión." }
    docker compose exec -T convolucion python3 -m scripts.experimentos directo `
        --entorno contenedor --practica02 /opt/practica02 --datos /opt/practica02/datos `
        --salida /app/resultados/mediciones/directo_contenedor.csv
    if ($LASTEXITCODE -ne 0) { throw "Fallo PyCUDA directo dentro del contenedor." }
    & $Python -m scripts.experimentos servicio --entorno cliente_local `
        --url http://127.0.0.1:8080 --salida resultados/mediciones/servicio.csv
    if ($LASTEXITCODE -ne 0) { throw "Fallaron las mediciones del servicio HTTP." }
    $ComandoValidacion = "call ..\GuillenJ_SolanoA_Practica0\scripts\entorno_vs.bat && $Python -m scripts.validar_servicio --url http://127.0.0.1:8080"
    cmd /d /s /c $ComandoValidacion
    if ($LASTEXITCODE -ne 0) { throw "La validación funcional o numérica reportó fallas." }
    $IdServicio = docker compose ps -q convolucion
    if (-not $IdServicio) { throw "No se pudo identificar el contenedor del servicio." }
    $RedServicio = docker inspect $IdServicio --format '{{range $nombre, $valor := .NetworkSettings.Networks}}{{$nombre}}{{end}}'
    if ($LASTEXITCODE -ne 0 -or -not $RedServicio) { throw "No se pudo identificar la red del servicio." }
    $EvidenciaCliente = docker run --rm --network $RedServicio --entrypoint python3 `
        convolucion-pycuda:p03 -m scripts.probar_cliente_distinto `
        --url http://convolucion:8000
    $CodigoCliente = $LASTEXITCODE
    $EvidenciaCliente | Set-Content -Encoding utf8 `
        -LiteralPath resultados/evidencia/cliente_distinto.json
    if ($CodigoCliente -ne 0) { throw "Falló la demostración desde el contenedor cliente separado." }

    # Misma imagen sin --gpus: debe responder 503 con diagnóstico, sin respaldo en CPU.
    cmd /d /c "docker rm -f p03_sin_gpu > nul 2>&1"
    docker run --detach --name p03_sin_gpu -p 8081:8000 convolucion-pycuda:p03 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "No se pudo iniciar el contenedor sin GPU." }
    try {
        & $Python -m scripts.probar_sin_gpu --url http://127.0.0.1:8081 `
            --imagen ..\GuillenJ_SolanoA_Practica0\datos\base_250.pgm `
            --salida resultados/evidencia/sin_gpu.json
        $CodigoSinGPU = $LASTEXITCODE
        cmd /d /c "docker logs p03_sin_gpu > resultados\evidencia\log_sin_gpu.txt 2>&1"
    } finally {
        cmd /d /c "docker rm -f p03_sin_gpu > nul 2>&1"
    }
    if ($CodigoSinGPU -ne 0) { throw "El servicio sin GPU no produjo el diagnóstico 503 esperado." }

    & $Python -m scripts.resumir_resultados `
        resultados/mediciones/directo_anfitrion.csv `
        resultados/mediciones/directo_contenedor.csv `
        resultados/mediciones/servicio.csv `
        --salida resultados/mediciones/resumen.csv
    if ($LASTEXITCODE -ne 0) { throw "No se pudo generar el resumen estadistico." }
    & $Python -m scripts.generar_graficas resultados/mediciones/resumen.csv `
        --salida resultados/graficas
    if ($LASTEXITCODE -ne 0) { throw "No se pudieron generar las graficas." }
    cmd /d /c "docker compose logs --no-color > resultados\evidencia\log_contenedor_final.txt 2>&1"
    if (-not $OmitirCopiaLimpia) {
        & .\verificar_copia_limpia.ps1 -Commit $CommitPractica03
    }
    & $Python -m scripts.verificar_resultados_finales
    if ($LASTEXITCODE -ne 0) { throw "La corrida final no contiene la matriz completa exigida." }
    Write-Host "Experimentos terminados. Revise CSV, gráficas y cualquier fila con error."
} finally {
    docker compose down
    Pop-Location
}
