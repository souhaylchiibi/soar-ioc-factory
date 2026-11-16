# Update TOC/fields with Microsoft Word, save the .docx and export a PDF.
# Usage: powershell -File scripts/word_finalize.ps1 <path.docx>
param([Parameter(Mandatory = $true)][string]$Docx)
$ErrorActionPreference = "Stop"
$full = (Resolve-Path $Docx).Path
$pdf = [System.IO.Path]::ChangeExtension($full, ".pdf")
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($full)
    foreach ($toc in $doc.TablesOfContents) { $toc.Update() }
    $doc.Fields.Update() | Out-Null
    foreach ($toc in $doc.TablesOfContents) { $toc.Update() }   # page numbers after layout
    $doc.Save()
    $doc.ExportAsFixedFormat($pdf, 17)   # wdExportFormatPDF
    "pages: " + $doc.ComputeStatistics(2)
    $doc.Close()
    "pdf: $pdf"
} finally {
    $word.Quit()
}
