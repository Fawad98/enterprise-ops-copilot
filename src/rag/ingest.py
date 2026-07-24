"""Chunk policy docs, embed, and push to Azure AI Search (hybrid index).

Note on endpoints: embeddings route to the ACCOUNT (base) endpoint, not the
/api/projects/... project endpoint. Using the project endpoint returns HTTP 404
on /embeddings. Chat and embeddings also need different API versions - see
docs/challenges-and-solutions.md entries 3 and 7.
"""
import glob
import hashlib
import os

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
INDEX = os.environ["AZURE_SEARCH_INDEX"]
EMBED_DEPLOYMENT = os.environ.get("AZURE_EMBED_DEPLOYMENT_NAME", "embed")
CRED = DefaultAzureCredential()

_token_provider = get_bearer_token_provider(CRED, "https://cognitiveservices.azure.com/.default")
openai_client = AzureOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    azure_ad_token_provider=_token_provider,
    api_version="2024-10-21",
)


def chunk(text: str, target: int = 800, overlap: int = 150) -> list[str]:
    """Paragraph-aware chunking with overlap. Simple beats clever here - see ADR 001."""
    paras, chunks, buf = text.split("\n\n"), [], ""
    for p in paras:
        if len(buf) + len(p) > target and buf:
            chunks.append(buf.strip())
            buf = buf[-overlap:] + "\n\n" + p
        else:
            buf += "\n\n" + p
    if buf.strip():
        chunks.append(buf.strip())
    return chunks


def embed(texts: list[str]) -> list[list[float]]:
    resp = openai_client.embeddings.create(model=EMBED_DEPLOYMENT, input=texts)
    return [d.embedding for d in resp.data]


def create_index() -> None:
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),
        SearchField(name="vector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True, vector_search_dimensions=1536,
                    vector_search_profile_name="vp"),
    ]
    vs = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
        profiles=[VectorSearchProfile(name="vp", algorithm_configuration_name="hnsw")],
    )
    sem = SemanticSearch(configurations=[SemanticConfiguration(
        name="sem", prioritized_fields=SemanticPrioritizedFields(
            content_fields=[SemanticField(field_name="content")]))])
    SearchIndexClient(ENDPOINT, CRED).create_or_update_index(
        SearchIndex(name=INDEX, fields=fields, vector_search=vs, semantic_search=sem))


def run() -> None:
    create_index()
    sc = SearchClient(ENDPOINT, INDEX, CRED)
    docs = []
    for path in glob.glob("data/policies/*.md"):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for i, ch in enumerate(chunk(text)):
            docs.append({"id": hashlib.md5(f"{path}-{i}".encode()).hexdigest(),
                         "content": ch, "source": os.path.basename(path)})
    vectors = embed([d["content"] for d in docs])
    for d, v in zip(docs, vectors, strict=True):
        d["vector"] = v
    sc.upload_documents(docs)
    print(f"Indexed {len(docs)} chunks into '{INDEX}'")


if __name__ == "__main__":
    run()