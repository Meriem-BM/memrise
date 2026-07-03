from memrise.graph.entities import default_node_type_for_memory, resolve_graph_node_type
from memrise.graph.retrieval import should_use_graph_retrieval
from memrise.graph.types import (
    RelationType,
    coerce_node_label,
    coerce_relation,
    normalize_entity_name,
)

__all__ = [
    "RelationType",
    "coerce_node_label",
    "coerce_relation",
    "default_node_type_for_memory",
    "normalize_entity_name",
    "resolve_graph_node_type",
    "should_use_graph_retrieval",
]


def build_graph_projection(*args, **kwargs):
    from memrise.graph.projection import build_graph_projection as _build

    return _build(*args, **kwargs)


__all__.append("build_graph_projection")
