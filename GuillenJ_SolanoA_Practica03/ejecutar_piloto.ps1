param(
    [string]$Python = ".\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $Raiz
try {
    if (-not (Test-Path -LiteralPath $Python)) {
        throw "No existe $Python. Cree .venv e instale requirements.txt."
    }
    # El piloto puede correr con cambios sin commit; la imagen queda marcada como tal.
    $Cabeza = git -C .. rev-parse HEAD
    $Sucio = @(git -C .. status --porcelain).Count -gt 0
    $env:COMMIT_PRACTICA03 = if ($Sucio) { "$Cabeza-con-cambios" } else { $Cabeza }
    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Las pruebas automatizadas fallaron." }
    & $Python -m scripts.registrar_entorno --entorno anfitrion
    if ($LASTEXITCODE -ne 0) { throw "No se pudo registrar el entorno anfitrion." }
    docker compose up --build --detach
    if ($LASTEXITCODE -ne 0) { throw "Fallo la construccion o el inicio del contenedor." }
    $Listo = $false
    for ($Intento = 1; $Intento -le 24; $Intento++) {
        try {
            Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/salud" -TimeoutSec 5 | Out-Null
            $Listo = $true
            break
        } catch {
            Start-Sleep -Seconds 5
        }
    }
    if (-not $Listo) { throw "El servicio no respondió después de 120 segundos." }

    docker compose exec -T convolucion nvidia-smi
    if ($LASTEXITCODE -ne 0) { throw "La GPU no esta visible dentro del contenedor." }
    docker compose exec -T convolucion python3 -m scripts.registrar_entorno --entorno contenedor
    if ($LASTEXITCODE -ne 0) { throw "No se pudo registrar el entorno del contenedor." }
    $ComandoDirecto = "call ..\GuillenJ_SolanoA_Practica0\scripts\entorno_vs.bat && $Python -m scripts.experimentos directo --piloto --repeticiones 1 --entorno anfitrion --salida resultados\mediciones\piloto_directo_anfitrion.csv"
    cmd /d /s /c $ComandoDirecto
    if ($LASTEXITCODE -ne 0) { throw "Falló el piloto PyCUDA directo en el anfitrión." }
    docker compose exec -T convolucion python3 -m scripts.experimentos directo --piloto --repeticiones 1 `
        --entorno contenedor --practica02 /opt/practica02 --datos /opt/practica02/datos `
        --salida /app/resultados/mediciones/piloto_directo_contenedor.csv
    if ($LASTEXITCODE -ne 0) { throw "Fallo el piloto PyCUDA directo en el contenedor." }
    & $Python -m scripts.experimentos servicio --piloto --repeticiones 1 --entorno cliente_local `
        --url http://127.0.0.1:8080 --salida resultados/mediciones/piloto_servicio.csv
    if ($LASTEXITCODE -ne 0) { throw "Fallo el piloto a traves del servicio HTTP." }
    $ComandoValidacion = "call ..\GuillenJ_SolanoA_Practica0\scripts\entorno_vs.bat && $Python -m scripts.validar_servicio --url http://127.0.0.1:8080 --omitir-archivo-grande --omitir-cola"
    cmd /d /s /c $ComandoValidacion
    if ($LASTEXITCODE -ne 0) { throw "La validación funcional o numérica reportó fallas." }
    docker compose logs --no-color | Set-Content -LiteralPath resultados/evidencia/log_contenedor_piloto.txt
    if ($LASTEXITCODE -ne 0) { throw "No se pudo guardar el log del contenedor." }
    Write-Host "Piloto y validación terminados. Revise resultados/."
} finally {
    docker compose down
    Pop-Location
}

