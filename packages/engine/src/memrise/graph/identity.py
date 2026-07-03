import hashlib

from memrise.graph.types import normalize_entity_name


def node_identity_key(*, namespace_id: str, node_type: str, name: str) -> str:
    return f"{namespace_id}:{node_type}:{normalize_entity_name(name)}"


def stable_entity_id(*, namespace_id: str, core_type: str, name: str) -> str:
    return f"gent-{node_identity_key(namespace_id=namespace_id, node_type=core_type, name=name)}"


def stable_claim_id(
    *,
    subject_entity_id: str,
    predicate: str,
    object_entity_id: str,
    memory_version_id: str,
) -> str:
    digest = hashlib.sha256(
        f"{subject_entity_id}:{predicate}:{object_entity_id}:{memory_version_id}".encode()
    ).hexdigest()[:24]
    return f"gclm-{digest}"


def age_node_uid(*, namespace_id: str, core_type: str, name: str) -> str:
    return f"node-{node_identity_key(namespace_id=namespace_id, node_type=core_type, name=name)}"
