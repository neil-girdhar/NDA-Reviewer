param(
    [switch]$DryRun,
    [switch]$Move
)

$ErrorActionPreference = 'Stop'

$sourceDir = "C:\Claude\Projects\Organized Files"
$destBase  = Join-Path $sourceDir "organized"
$logPath   = "C:\Claude\Projects\NDA Reviewer\organize_log.csv"

$knownNdaTypes       = @('MNDA','MDNA','3NDA','PSA','DPA','MSA','NDA','NO')
$knownCorpBUs        = @('ATHIV','BPGHIVC','NA','APAC','ATAEA','TIT','ASP','NACSUS')
$knownMlsSubEntities = @('DKUS','NACS','KORVIS','KOV','ASP','NACSUS')
$knownMlsSites       = @('LS','AM','DEV','AA','NA')

function Get-NdaType([string]$token) {
    # Strip trailing punctuation, then check exact match or suffix match
    $t = $token.Trim().TrimEnd('.')
    foreach ($type in $knownNdaTypes) {
        if ($t -eq $type) { return $type }
        # Handle prefix like "1st Amendment MNDA"
        if ($t.EndsWith(" $type")) { return $type }
    }
    return $null
}

function Parse-NdaFile([System.IO.FileInfo]$file) {
    $stem = [System.IO.Path]::GetFileNameWithoutExtension($file.Name)

    # Normalize spaces around hyphens, then collapse runs of hyphens
    $norm = $stem -replace '\s*-\s*', '-'
    $norm = ($norm -replace '-+', '-').Trim('-').Trim()

    $parts = ($norm -split '-') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' }

    $result = [PSCustomObject]@{
        OriginalPath = $file.FullName
        ParsedType   = $null
        ParsedEntity = $null
        ParsedSite   = $null
        ParsedRegion = $null
        Counterparty = $null
        DestFolder   = '_unclassified'
        Status       = 'unclassified'
    }

    if ($parts.Count -lt 3) { return $result }

    # Position 0: NDA type
    $ndaType = Get-NdaType $parts[0]
    if (-not $ndaType) { return $result }
    $result.ParsedType = $ndaType

    if ($parts.Count -lt 4) { return $result }

    # Position 1: Legal entity
    $entity = $parts[1].ToUpper()
    $result.ParsedEntity = $entity

    switch ($entity) {
        'CORP' {
            $result.ParsedSite   = if ($parts.Count -gt 2) { $parts[2] } else { 'other' }
            $bu                  = if ($parts.Count -gt 3) { $parts[3] } else { 'other' }
            $result.ParsedRegion = $bu
            if ($parts.Count -gt 4) {
                $result.Counterparty = ($parts[4..($parts.Count - 1)]) -join '-'
            }
            $buFolder = if ($bu -in $knownCorpBUs) { $bu } else { 'other' }
            $result.DestFolder = "CORP\$ndaType\$buFolder"
            $result.Status     = 'parsed'
        }
        'MLS' {
            $result.ParsedSite   = if ($parts.Count -gt 2) { $parts[2] } else { 'other' }
            $result.ParsedRegion = if ($parts.Count -gt 3) { $parts[3] } else { 'other' }
            $subEntity           = if ($parts.Count -gt 4) { $parts[4].ToUpper() } else { $null }
            if ($parts.Count -gt 5) {
                $result.Counterparty = ($parts[5..($parts.Count - 1)]) -join '-'
            }
            if ($subEntity -and ($subEntity -in $knownMlsSubEntities)) {
                $result.ParsedEntity = "MLS-$subEntity"
                $mlsFolder           = "MLS-$subEntity"
            } else {
                $mlsFolder = 'MLS-other'
            }
            $siteFolder = if ($result.ParsedSite -in $knownMlsSites) { $result.ParsedSite } else { 'other' }
            $result.DestFolder = "$mlsFolder\$ndaType\$siteFolder"
            $result.Status     = 'parsed'
        }
        'TM' {
            $result.ParsedSite   = if ($parts.Count -gt 2) { $parts[2] } else { 'other' }
            $result.ParsedRegion = if ($parts.Count -gt 3) { $parts[3] } else { 'other' }
            $result.DestFolder   = "TM\$ndaType"
            $result.Status       = 'parsed'
        }
        default {
            # Parseable but unknown entity → other/[NDA-Type]/
            $result.DestFolder = "other\$ndaType"
            $result.Status     = 'parsed'
        }
    }

    return $result
}

# Scan all .md files, skip entity_list.md and anything already in organized\
$files = Get-ChildItem -Path $sourceDir -Recurse -Filter '*.md' |
    Where-Object {
        $_.Name -ne 'entity_list.md' -and
        $_.FullName -notlike "*\organized\*"
    }

Write-Host "Found $($files.Count) markdown files to process."

$log = [System.Collections.Generic.List[PSCustomObject]]::new()

foreach ($file in $files) {
    $parsed = Parse-NdaFile $file
    $log.Add($parsed)

    if ($DryRun) {
        Write-Host "[DRY RUN] [$($parsed.DestFolder)] $($file.Name)"
    } else {
        $destFolder = Join-Path $destBase $parsed.DestFolder
        $destFile   = Join-Path $destFolder $file.Name

        if (-not (Test-Path $destFolder)) {
            New-Item -ItemType Directory -Force -Path $destFolder | Out-Null
        }

        if ($Move) {
            Move-Item -Path $file.FullName -Destination $destFile -Force
            $parsed.Status = 'moved'
        } else {
            Copy-Item -Path $file.FullName -Destination $destFile -Force
            $parsed.Status = 'copied'
        }

        Write-Host "[$($parsed.DestFolder)] $($file.Name)"
    }
}

$log | Export-Csv -Path $logPath -NoTypeInformation -Encoding UTF8
Write-Host ""
Write-Host "Log written to: $logPath"
Write-Host "Total files processed: $($log.Count)"
Write-Host ""
Write-Host "--- Bucket Summary ---"
$log | Group-Object DestFolder | Sort-Object Count -Descending | ForEach-Object {
    Write-Host "$($_.Count.ToString().PadLeft(4))  $($_.Name)"
}
