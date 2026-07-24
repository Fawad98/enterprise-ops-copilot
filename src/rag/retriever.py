import os
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from opentelemetry import trace

tracer = trace.get_tracer("zavaops.rag")


def hybrid_search(query: str, query_vector: list[float], k: int = 4) -> list[dict]:
    """Hybrid (BM25 + vector) with semantic reranking.

    Emits a `rag.hybrid_search` span carrying retrieval *quality* attributes
    (top reranker score, sources, result count) so traces show not just how long
    retrieval took but how well it did - see ADR 001.
    """
    with tracer.start_as_current_span("rag.hybrid_search") as span:
        span.set_attribute("rag.query", query[:200])
        span.set_attribute("rag.k", k)

        sc = SearchClient(os.environ["AZURE_SEARCH_ENDPOINT"],
                          os.environ["AZURE_SEARCH_INDEX"], DefaultAzureCredential())
        results = sc.search(
            search_text=query,
            vector_queries=[VectorizedQuery(vector=query_vector, k_nearest_neighbors=8, fields="vector")],
            query_type="semantic", semantic_configuration_name="sem",
            top=k,
        )
        hits = [{"content": r["content"], "source": r["source"],
                 "score": r["@search.reranker_score"]} for r in results]

        span.set_attribute("rag.result_count", len(hits))
        if hits:
            span.set_attribute("rag.top_score", float(hits[0]["score"]))
            span.set_attribute("rag.min_score", float(hits[-1]["score"]))
            span.set_attribute("rag.sources", ",".join(h["source"] for h in hits))
        else:
            span.set_attribute("rag.top_score", 0.0)
            span.set_attribute("rag.no_results", True)

        return hits
    