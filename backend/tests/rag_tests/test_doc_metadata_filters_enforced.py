from app.rag.retriever import KnowledgeRetriever


def test_retriever_respects_allowed_metadata_types() -> None:
    retriever = KnowledgeRetriever(
        [
            {
                "doc_id": "policy-doc",
                "title": "Policy",
                "text": "Fee policy details.",
                "metadata": {"type": "policy"},
            },
            {
                "doc_id": "faq-doc",
                "title": "FAQ",
                "text": "General help details.",
                "metadata": {"type": "faq"},
            },
        ]
    )

    result = retriever.retrieve("fee policy", allowed_types=("policy",))

    assert len(result.citations) == 1
    assert result.citations[0]["doc_id"] == "policy-doc"
