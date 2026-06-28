"""GraphStore — the swap seam over the knowledge graph (§13).

All graph access sits behind the ``GraphStore`` ABC so the engine is swappable
(Neo4j Community now; embedded forks later). Cypher transfers across.
"""

from .base import GraphStore
from .neo4j_store import Neo4jGraphStore

__all__ = ["GraphStore", "Neo4jGraphStore"]
