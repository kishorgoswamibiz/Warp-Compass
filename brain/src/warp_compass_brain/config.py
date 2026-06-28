"""Environment-driven configuration for the brain. See brain/.env.example."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Loaded from environment / a local .env file (never commit secrets)."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Neo4j (the unified graph) ---
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "warpcompass"
    neo4j_database: str = "neo4j"

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

    # --- Review queues (Phase 2) ---
    quarantine_path: str = "./_state/quarantine.jsonl"
    pending_taxonomy_path: str = "./_state/pending_taxonomy.jsonl"

    # --- Sync bus (Phase 8) ---
    bus_root: str = "./_bus"


def get_settings() -> Settings:
    return Settings()
