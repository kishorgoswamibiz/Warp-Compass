# Warp Compass — run one batch round (Phase 8), Windows/PowerShell variant of run-round.sh.
#
# One round = collect new Answer Logs -> register new participants -> ingest into the single
# Neo4j graph -> re-plan -> write each persona's next Session Brief back to its folder. Resumable.
#
# Prereqs: Neo4j Desktop Started; brain/.env has the DeepSeek key.
# Usage:   .\scripts\run-round.ps1 [--session s_2026_0630] [--bus C:\path\to\bus]
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $here "..\brain")

Write-Host "[warp-compass] round start"
uv run python -m warp_compass_brain.cli run-round @args
Write-Host "[warp-compass] round done."
