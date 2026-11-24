# Exporta a PDF el informe de la practica 03 con Microsoft Word.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\exportar_pdf.ps1
$ErrorActionPreference = "Stop"
$docs = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) "docs"
$docx = Join-Path $docs "informe\informe_practica03.docx"
$pdf = [IO.Path]::ChangeExtension($docx, ".pdf")
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $doc = $word.Documents.Open($docx, $false, $true)
    $doc.SaveAs([ref]$pdf, [ref]17)   # 17 = wdFormatPDF
    $doc.Close([ref]$false)
} finally { $word.Quit() }
Write-Output "PDF: $pdf"
