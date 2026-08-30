# Copy Firmware/src -> the CIRCUITPY drive (found by volume label).
# Non-destructive (/E, no /MIR): device-side lib/ and fonts/ you installed
# from the Adafruit bundle are never deleted by a deploy.
$vol = Get-Volume | Where-Object { $_.FileSystemLabel -eq "CIRCUITPY" }
if (-not $vol) {
    Write-Error "CIRCUITPY drive not found - is the Feather plugged in?"
    exit 1
}
$dst = "$($vol.DriveLetter):\"
$src = Join-Path $PSScriptRoot "..\src"

# Check the drive is writable BEFORE copying. CIRCUITPY goes read-only often
# enough that this has cost real debugging time, and robocopy hides it: on a
# write-protected drive it logs "ERROR 19 ... media is write protected" per
# directory but still exits 2 ("extra files detected"), which is below the
# usual >= 8 failure threshold. The old script printed "Deployed" and copied
# nothing.
$probe = Join-Path $dst ".deploy_write_test"
try {
    [IO.File]::WriteAllText($probe, "x")
    Remove-Item $probe -Force -ErrorAction SilentlyContinue
} catch {
    Write-Host "CIRCUITPY ($dst) is READ-ONLY - nothing was copied." -ForegroundColor Red
    Write-Host ""
    Write-Host "In an ELEVATED PowerShell, run:" -ForegroundColor Yellow
    Write-Host '  Get-Volume | Where-Object FileSystemLabel -eq CIRCUITPY | Get-Partition | ForEach-Object { Set-Disk -Number $_.DiskNumber -IsReadOnly $false }'
    exit 1
}

# /R:2 /W:2 because robocopy defaults to a million retries 30 seconds apart,
# which turns any transient failure into a deploy that hangs for days.
# /XF *.bdf: the device loads PCF now. The .bdf files stay in the repo as the
# source tools/render.py and tools/bdf2pcf.py read, but shipping them too
# would put 660 KB of dead weight on the device.
$out = robocopy $src $dst /E /NFL /NDL /NJH /NJS /R:2 /W:2 /XF *.bdf
$code = $LASTEXITCODE
$errors = $out | Select-String -SimpleMatch "ERROR"
if ($code -ge 8 -or $errors) {
    Write-Host "robocopy failed (exit $code)" -ForegroundColor Red
    $errors | ForEach-Object { Write-Host "  $_" }
    exit 1
}
Write-Host "Deployed src/ to $dst (device auto-reloads)."
exit 0
