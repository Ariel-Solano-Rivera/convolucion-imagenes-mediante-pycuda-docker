# Exporta a PDF el informe (.docx) y la presentacion (.pptx) con Microsoft Word y PowerPoint.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\exportar_pdf.ps1 [-Solo informe|presentacion]
param([string]$Solo = "")
$ErrorActionPreference = "Stop"
$docs = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) "docs"
if ($Solo -ne "presentacion") {
    $docx = Join-Path $docs "informe\informe_practica02.docx"
    $pdf = [IO.Path]::ChangeExtension($docx, ".pdf")
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    try {
        $doc = $word.Documents.Open($docx, $false, $true)
        $doc.SaveAs([ref]$pdf, [ref]17)   # 17 = wdFormatPDF
        $doc.Close([ref]$false)
    } finally { $word.Quit() }
    Write-Output "PDF: $pdf"
}
if ($Solo -ne "informe") {
    $pptx = Join-Path $docs "presentacion\presentacion_practica02.pptx"
    $pdf = [IO.Path]::ChangeExtension($pptx, ".pdf")
    $ppt = New-Object -ComObject PowerPoint.Application
    try {
        $pres = $ppt.Presentations.Open($pptx, $true, $false, $false)  # solo lectura, sin ventana
        $pres.SaveAs($pdf, 32)   # 32 = ppSaveAsPDF
        $pres.Close()
    } finally { $ppt.Quit() }
    Write-Output "PDF: $pdf"
}
