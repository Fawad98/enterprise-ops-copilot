import os
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

def hybrid_search(query: str, query_vector: list[float], k: int = 4) -> list[dict]:
    """Hybrid (BM25 + vector) with semantic reranking."""
    sc = SearchClient(os.environ["AZURE_SEARCH_ENDPOINT"],
                      os.environ["AZURE_SEARCH_INDEX"], DefaultAzureCredential())
    results = sc.search(
        search_text=query,
        vector_queries=[VectorizedQuery(vector=query_vector, k_nearest_neighbors=8, fields="vector")],
        query_type="semantic", semantic_configuration_name="sem",
        top=k,
    )
    return [{"content": r["content"], "source": r["source"],
             "score": r["@search.reranker_score"]} for r in results]