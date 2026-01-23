import os
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

class Neo4jClient:
    def __init__(self) -> None:
        self.uri = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "test12345")
        self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def close(self) -> None:
        if self._driver:
            self._driver.close()

    def ping(self) -> bool:
        try:
            with self._driver.session() as s:
                s.run("RETURN 1").consume()
            return True
        except ServiceUnavailable:
            return False

    def init_schema(self) -> None:
        """Create minimal constraints + fulltext index for 'memories'."""
        statements = [
            "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
            "CREATE CONSTRAINT memory_id IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE",
            "CREATE FULLTEXT INDEX memoryText IF NOT EXISTS FOR (m:Memory) ON EACH [m.text]",
        ]
        with self._driver.session() as s:
            for stmt in statements:
                s.run(stmt).consume()

    def add_memory(self, user_id: str, text: str, memory_id: str, created_at: str) -> None:
        cypher = """
        MERGE (u:User {id: $user_id})
        CREATE (m:Memory {id: $memory_id, user_id: $user_id, text: $text, created_at: $created_at})
        MERGE (u)-[:HAS_MEMORY]->(m)
        """
        with self._driver.session() as s:
            s.run(cypher, user_id=user_id, memory_id=memory_id, text=text, created_at=created_at).consume()

    def search_memories(self, user_id: str, q: str, limit: int):
        # Full-text search (Neo4j index must exist)
        cypher = """
        CALL db.index.fulltext.queryNodes('memoryText', $q) YIELD node, score
        WHERE node.user_id = $user_id
        RETURN node.id AS id, node.text AS text, node.created_at AS created_at, score
        ORDER BY score DESC
        LIMIT $limit
        """
        with self._driver.session() as s:
            result = s.run(cypher, user_id=user_id, q=q, limit=limit)
            return [r.data() for r in result]
