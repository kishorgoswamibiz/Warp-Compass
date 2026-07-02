"""GraphStore — the swap seam over the knowledge graph (§13).

All graph access sits behind the ``GraphStore`` ABC so the storage is swappable.
Since P12 the store is an OKF Markdown bundle — one readable file per node, no DB server.
"""

from .base import GraphStore
from .okf_store import OkfGraphStore

__all__ = ["GraphStore", "OkfGraphStore"]
