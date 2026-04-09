$ErrorActionPreference = "SilentlyContinue"

function Remove-PyCacheArtifacts {
    param([string]$Path)

    if (-not $Path) { return }

    if (Test-Path -LiteralPath $Path) {
        $item = Get-Item -LiteralPath $Path -ErrorAction SilentlyContinue
        if ($null -eq $item) { return }

        if ($item.PSIsContainer -and $item.Name -eq "__pycache__") {
            Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue
            return
        }

        if (-not $item.PSIsContainer -and ($item.Extension -eq ".pyc" -or $item.Extension -eq ".pyo")) {
            Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
            return
        }
    }

    if ($Path -match "__pycache__") {
        Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# Initial cleanup
& "$PSScriptRoot\clean_pycache.ps1" | Out-Null

$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = (Get-Location).Path
$watcher.IncludeSubdirectories = $true
$watcher.EnableRaisingEvents = $true
$watcher.Filter = "*"

$created = Register-ObjectEvent -InputObject $watcher -EventName Created -Action {
    Remove-PyCacheArtifacts -Path $Event.SourceEventArgs.FullPath
}
$changed = Register-ObjectEvent -InputObject $watcher -EventName Changed -Action {
    Remove-PyCacheArtifacts -Path $Event.SourceEventArgs.FullPath
}
$renamed = Register-ObjectEvent -InputObject $watcher -EventName Renamed -Action {
    Remove-PyCacheArtifacts -Path $Event.SourceEventArgs.FullPath
}

Write-Host "Watching for __pycache__/.pyc/.pyo and deleting immediately..."

try {
    while ($true) {
        Wait-Event -Timeout 2 | Out-Null
    }
}
finally {
    Unregister-Event -SourceIdentifier $created.Name -ErrorAction SilentlyContinue
    Unregister-Event -SourceIdentifier $changed.Name -ErrorAction SilentlyContinue
    Unregister-Event -SourceIdentifier $renamed.Name -ErrorAction SilentlyContinue
    $watcher.Dispose()
}
