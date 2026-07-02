from memrise.graph.query_planner import should_use_graph_retrieval


def test_should_use_graph_retrieval_for_relation_queries() -> None:
    assert should_use_graph_retrieval("What does Atlas depend on?")
    assert should_use_graph_retrieval("Who owns the Atlas project?")


def test_should_not_use_graph_retrieval_for_generic_prompts() -> None:
    assert not should_use_graph_retrieval("")
    assert not should_use_graph_retrieval("Summarize the tone for this response.")
