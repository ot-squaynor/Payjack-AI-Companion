from app.rag.retriever import KnowledgeRetriever


def test_retriever_returns_citable_chunks() -> None:
    retriever = KnowledgeRetriever(
        [
            {
                "doc_id": "fees-policy",
                "title": "Fees Policy",
                "text": "Payjack fee explanations are available in the help center.",
                "metadata": {"type": "policy", "source_path": "policies/fees.md"},
            }
        ]
    )

    result = retriever.retrieve("Where can I find fee explanations?")

    assert len(result.citations) == 1
    citation = result.citations[0]
    assert citation["doc_id"] == "fees-policy"
    assert citation["title"] == "Fees Policy"
    assert "help center" in citation["snippet"]
    assert citation["metadata"]["type"] == "policy"
