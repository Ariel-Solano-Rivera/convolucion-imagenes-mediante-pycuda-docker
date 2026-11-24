# Clona el commit indicado en una carpeta temporal y construye la imagen desde esa copia
# limpia (sin .venv, runtime ni archivos sin versionar). Guarda el log y el ID de imagen.
param(
    [string]$Commit = "",
    [string]$Destino = (Join-Path $env:TEMP "p03_copia_limpia")
)

$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $Raiz
try {
    if (-not $Commit) {
        $Commit = git -C .. rev-parse HEAD
        if ($LASTEXITCODE -ne 0) { throw "No se pudo determinar el commit." }
    }
    if (-not $Commit) { throw "No se pudo determinar el commit." }
    if (Test-Path -LiteralPath $Destino) { Remove-Item -LiteralPath $Destino -Recurse -Force }
    $Repositorio = (Resolve-Path ..).Path
    git clone --quiet --no-local $Repositorio $Destino
    if ($LASTEXITCODE -ne 0) { throw "Falló git clone de la copia limpia." }
    git -C $Destino checkout --quiet $Commit
    if ($LASTEXITCODE -ne 0) { throw "No existe el commit $Commit en la copia." }

    $Contexto = Join-Path $Destino "GuillenJ_SolanoA_Practica03"
    $ContextoP02 = Join-Path $Destino "GuillenJ_SolanoA_Practica0"
    $Log = Join-Path $Raiz "resultados\evidencia\construccion_copia_limpia.txt"
    $Etiqueta = "convolucion-pycuda:p03-copia-limpia"
    # cmd evita que PowerShell 5.1 convierta la salida de error de docker en excepciones.
    cmd /d /c "docker build --progress=plain --build-context practica02=`"$ContextoP02`" --build-arg COMMIT_PRACTICA03=$Commit -t $Etiqueta `"$Contexto`" > `"$Log`" 2>&1"
    $Codigo = $LASTEXITCODE
    $IdImagen = if ($Codigo -eq 0) { docker image inspect $Etiqueta --format "{{.Id}}" } else { "" }
    # Se leen las etiquetas como JSON: PowerShell 5.1 elimina las comillas internas de una
    # plantilla como {{index .Config.Labels "..."}} al pasarla a docker.
    $Revision = if ($Codigo -eq 0) {
        $Etiquetas = docker image inspect $Etiqueta --format "{{json .Config.Labels}}" | ConvertFrom-Json
        [string]$Etiquetas.'org.opencontainers.image.revision'
    } else { "" }
    $Evidencia = [ordered]@{
        fecha             = (Get-Date).ToString("s")
        commit_clonado    = $Commit
        carpeta_copia     = $Destino
        comando           = "docker build --build-context practica02=<copia>/GuillenJ_SolanoA_Practica0 --build-arg COMMIT_PRACTICA03=$Commit -t $Etiqueta <copia>/GuillenJ_SolanoA_Practica03"
        codigo_salida     = $Codigo
        id_imagen         = $IdImagen
        revision_etiqueta = $Revision
        resultado         = $(if ($Codigo -eq 0 -and $Revision -eq $Commit) { "OK" } else { "FALLA" })
    }
    $Evidencia | ConvertTo-Json | Set-Content -Encoding utf8 -LiteralPath "resultados\evidencia\copia_limpia.json"
    if ($Evidencia.resultado -ne "OK") { throw "La construcción desde copia limpia falló; revise $Log." }
    Write-Host "Copia limpia construida: $IdImagen (commit $Commit)"
} finally {
    Pop-Location
}
