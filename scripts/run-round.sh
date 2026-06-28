#!/usr/bin/env bash
# Warp Compass — run one batch round (Phase 8).
#
# One round = collect every participant's NEW Answer Logs -> register any new participant ->
# ingest into the single Neo4j graph (extract -> resolve -> create-gate) -> re-plan ->
# write each persona's next Session Brief back to its folder. Resumable: re-running after a
# transient failure skips logs already ingested (tracked in each profile.json).
#
# Prereqs: Neo4j Desktop Started; brain/.env has the DeepSeek key. Run from anywhere.
# Usage:   scripts/run-round.sh [--session s_2026_0630] [--bus /path/to/bus]
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "${HERE}/../brain"

echo "[warp-compass] round start"
# Pass --bus to override; otherwise the brain uses settings.bus_root (./_bus, relative to brain/).
uv run python -m warp_compass_brain.cli run-round "$@"
echo "[warp-compass] round done."
