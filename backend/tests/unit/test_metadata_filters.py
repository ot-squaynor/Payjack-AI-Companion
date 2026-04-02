from app.rag.metadata_filters import apply_metadata_filters


def test_metadata_filters_allow_only_requested_types() -> None:
    chunks = [
        {"doc_id": "doc-1", "metadata": {"type": "policy"}},
        {"doc_id": "doc-2", "metadata": {"type": "faq"}},
    ]

    filtered = apply_metadata_filters(chunks, allowed_types=("policy",))

    assert filtered == [chunks[0]]


def test_metadata_filters_return_all_chunks_without_type_constraints() -> None:
    chunks = [
        {"doc_id": "doc-1", "metadata": {"type": "policy"}},
        {"doc_id": "doc-2", "metadata": {"type": "faq"}},
    ]

    assert apply_metadata_filters(chunks) == chunks
