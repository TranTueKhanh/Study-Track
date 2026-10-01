Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptRoot
$mainScript = Join-Path $projectRoot "main.py"
$distRoot = Join-Path $projectRoot "dist"
$workRoot = Join-Path $projectRoot "build"

if (-not (Test-Path $mainScript)) {
    throw "Cannot find app entry point: $mainScript"
}

$pyInstallerArgs = @(
    "--noconfirm"
    "--clean"
    "--windowed"
    "--name"
    "StudyTrack"
    "--distpath"
    $distRoot
    "--workpath"
    $workRoot
    "--specpath"
    $projectRoot
    "--add-data"
    "$projectRoot\ui;ui"
    "--add-data"
    "$projectRoot\data;data"
    "--hidden-import"
    "PyQt6.QtCharts"
    $mainScript
)

python -m PyInstaller @pyInstallerArgs

Write-Host ""
Write-Host "Build completed."
Write-Host "Executable: $distRoot\StudyTrack\StudyTrack.exe"
