"""Environment-driven configuration for the brain. See brain/.env.example."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Loaded from environment / a local .env file (never commit secrets)."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- The unified graph: an OKF Markdown bundle (P12). Empty = {bus_root}/graph, i.e.
    # inside the Drive-synced engagement folder, so the knowledge base syncs/backs up for free.
    # Set GRAPH_ROOT in brain/.env to override (e.g. keep the graph local-only). ---
    graph_root: str = ""

    # --- Paid APIs. For LIVE calls keys live only in the Worker, never the browser;
    # these brain-side keys are for batch use (extraction/adjudication). ---
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    elevenlabs_api_key: str = ""

    # DeepSeek model IDs. Defaults follow the design doc; CONFIRM against `/models` once a key
    # is set (run `python -m warp_compass_brain.cli check-models`). If your account only exposes
    # the classic IDs, set DEEPSEEK_MODEL_BATCH=deepseek-reasoner and
    # DEEPSEEK_MODEL_LIVE=deepseek-chat in brain/.env.
    deepseek_model_batch: str = "deepseek-v4-pro"
    deepseek_model_live: str = "deepseek-v4-flash"

    # --- Resolve / create-gate tuning (Phase 2) ---
    similarity_ceiling: float = 0.86  # >= this vs an existing node overrules an LLM "new" verdict
    retrieval_top_k: int = 8          # candidate cards shown to the adjudicator

    # --- Local embeddings + vector store (Phase 2) ---
    embedding_model: str = "BAAI/bge-small-en-v1.5"  # fastembed (ONNX, local, free)
    vector_db_path: str = "./_state/vectors.sqlite"

    # --- Completeness / "satisfaction" thresholds (Phase 3) — tunable; DECISION open (#16).
    # The org is reported "satisfied" only when every persona score and the org score clear
    # these bars AND the open-thread list is empty. Higher = pester more; lower = stop early. ---
    persona_satisfied_threshold: float = 0.9
    org_satisfied_threshold: float = 0.9

    # --- Planner / Session Brief (Phase 4) ---
    planner_max_threads: int = 6  # top-N threads carried in a brief; the rest go to reserve_threads
    # P13: questions inherited from retired teammates, appended BELOW a person's own threads. Keep
    # it small — they're someone else's process, and too many turns a brief into a quiz.
    planner_orphan_max: int = 2
    # P16a-bis: open questions on a role this person DECLARED but hasn't personally described,
    # appended below their own work. Larger than the orphan cap on purpose — this is their own job,
    # not a departed colleague's — but still capped, because a newly joined holder of a well-covered
    # role would otherwise get a brief made entirely of other people's accounts (phase-16 R6).
    planner_role_max: int = 4

    # --- Review queues (Phase 2) ---
    quarantine_path: str = "./_state/quarantine.jsonl"
    pending_taxonomy_path: str = "./_state/pending_taxonomy.jsonl"

    # --- Sync bus (Phase 8) ---
    bus_root: str = "./_bus"

    # --- Sync-drive resilience (P14). A Google-Drive-backed bus fails *whole*: when its user-mode
    # FS driver runs out of resources, every operation on the drive — reads and `stat` included —
    # returns WinError 1450, which used to abort a round outright. `fsretry` backs off and retries.
    # The default schedule spans ~15s per operation (0.5+1+2+4+8s); attempts=1 disables it. ---
    fs_retry_attempts: int = 6
    fs_retry_base_delay: float = 0.5

    # --- Empty-completion retry. The openai SDK retries HTTP errors, but a 200 with an empty or
    # non-JSON body isn't an error to it — and the batch model emits one occasionally, which used
    # to abort a round. Re-asking usually succeeds; attempts=1 disables it. ---
    llm_json_attempts: int = 3
    llm_json_base_delay: float = 1.0


def get_settings() -> Settings:
    return Settings()


def resolve_graph_root(settings: Settings) -> str:
    """Where the OKF graph bundle lives: GRAPH_ROOT if set, else ``{bus_root}/graph``."""
    if settings.graph_root:
        return settings.graph_root
    from pathlib import Path

    return str(Path(settings.bus_root) / "graph")
