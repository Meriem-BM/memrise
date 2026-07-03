from memrise.graph.retrieval import should_use_graph_retrieval


def test_should_use_graph_retrieval_for_relation_queries() -> None:
    assert should_use_graph_retrieval("Who works on Atlas?")
    assert should_use_graph_retrieval("What depends on PostgreSQL?")


def test_should_not_use_graph_retrieval_for_generic_prompts() -> None:
    assert not should_use_graph_retrieval("Summarize this in bullet points")
    assert not should_use_graph_retrieval("")
