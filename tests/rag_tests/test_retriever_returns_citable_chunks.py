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

    assert result.usable_context is True
    assert len(result.citations) == 1
    assert result.accepted_count == 1
    assert result.retrieved_count == 1
    assert result.top_score > 0
    citation = result.citations[0]
    assert citation["doc_id"] == "fees-policy"
    assert citation["title"] == "Fees Policy"
    assert "help center" in citation["snippet"]
    assert citation["metadata"]["type"] == "policy"


def test_retriever_rejects_irrelevant_context_and_falls_back() -> None:
    retriever = KnowledgeRetriever(
        [
            {
                "doc_id": "refer-and-earn",
                "title": "Refer And Earn",
                "text": "Share your referral link with friends and track rewards in the app.",
                "metadata": {"type": "feature"},
            },
            {
                "doc_id": "transaction-history",
                "title": "Transaction History",
                "text": "Review previous transfers and filter the result by date.",
                "metadata": {"type": "feature"},
            },
        ]
    )

    result = retriever.retrieve("What are the Payjack fees and limits?")

    assert result.usable_context is False
    assert result.citations == ()
    assert result.accepted_count == 0
    assert result.fallback_reason in {"insufficient_term_overlap", "insufficient_title_overlap", "no_candidate_chunks"}
