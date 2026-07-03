from memrise.graph.types import coerce_node_label, coerce_relation

GRAPH_NAME = "memrise_graph"

MATCH_NODE_BY_IDENTITY = """
MATCH (n:{label} {{
  namespace_id: $namespace_id,
  type: $type,
  normalized_name: $normalized_name
}})
RETURN n
LIMIT 1
"""

CREATE_NODE = """
CREATE (n:{label} {{
  uid: $uid,
  namespace_id: $namespace_id,
  type: $type,
  canonical_name: $canonical_name,
  normalized_name: $normalized_name,
  aliases: $aliases,
  created_at: $created_at
}})
RETURN n
"""

UPDATE_NODE_ALIASES = """
MATCH (n:{label} {{uid: $uid, namespace_id: $namespace_id}})
SET n.aliases = $aliases
RETURN n
"""

CREATE_EDGE = """
MATCH (source:{source_label} {{uid: $source_uid, namespace_id: $namespace_id}})
MATCH (target:{target_label} {{uid: $target_uid, namespace_id: $namespace_id}})
CREATE (source)-[r:{relation} {{
  uid: $edge_uid,
  namespace_id: $namespace_id,
  source_uid: $source_uid,
  target_uid: $target_uid,
  relation: $relation_name,
  source_memory_version_id: $source_memory_version_id,
  claim_id: $claim_id,
  status: $status,
  confidence: $confidence,
  usefulness_score: $usefulness_score,
  valid_from: $valid_from,
  valid_until: $valid_until
}}]->(target)
RETURN r
"""

EDGE_EXISTS = """
MATCH ()-[r {uid: $edge_uid}]->()
RETURN r
LIMIT 1
"""

EDGES_FOR_MEMORY_VERSION = """
MATCH ()-[r]->()
WHERE r.namespace_id = $namespace_id
  AND r.source_memory_version_id = $memory_version_id
RETURN r
"""

SUPERSEDE_EDGES_FOR_VERSION = """
MATCH ()-[r]->()
WHERE r.source_memory_version_id = $memory_version_id
  AND r.namespace_id = $namespace_id
  AND r.status = 'active'
SET r.status = 'superseded', r.valid_until = $valid_until
RETURN count(r) AS superseded_count
"""

UPDATE_EDGE_USEFULNESS = """
MATCH ()-[r {uid: $edge_uid}]->()
SET r.usefulness_score = $usefulness_score
RETURN r
"""

ONE_HOP_NEIGHBORHOOD = """
MATCH (seed)-[r]-(neighbor)
WHERE seed.namespace_id = $namespace_id
  AND seed.normalized_name CONTAINS $term
  AND r.namespace_id = $namespace_id
  AND r.status = 'active'
  AND (r.valid_until IS NULL OR r.valid_until > $now)
RETURN seed, r, neighbor
LIMIT $limit
"""

TWO_HOP_PATH = """
MATCH (seed)-[r1]-(mid)-[r2]-(leaf)
WHERE seed.namespace_id = $namespace_id
  AND seed.normalized_name CONTAINS $term
  AND r1.namespace_id = $namespace_id
  AND r2.namespace_id = $namespace_id
  AND r1.status = 'active'
  AND r2.status = 'active'
  AND (r1.valid_until IS NULL OR r1.valid_until > $now)
  AND (r2.valid_until IS NULL OR r2.valid_until > $now)
RETURN seed, r1, mid, r2, leaf
LIMIT $limit
"""


def node_label(node_type: str) -> str:
    return coerce_node_label(node_type)


def relation_label(relation: str) -> str:
    return coerce_relation(relation)
