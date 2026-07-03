from memrise.write.importance import ImportanceGate

GATE = ImportanceGate()


def test_ordinary_sentences_without_markers_are_extracted() -> None:
    assert GATE.should_extract("My name is Meriem.")
    assert GATE.should_extract("The staging database is db-eu-2.")
    assert GATE.should_extract("Deploys happen on Fridays.")


def test_empty_and_trivial_acknowledgements_are_skipped() -> None:
    assert not GATE.should_extract("")
    assert not GATE.should_extract("   ")
    assert not GATE.should_extract("ok")
    assert not GATE.should_extract("thanks!")


def test_short_imperatives_with_markers_are_extracted() -> None:
    assert GATE.should_extract("use pnpm")
    assert GATE.should_extract("never force-push")
