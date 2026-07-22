"""Chunk policy docs, embed, and push to Azure AI Search (hybrid index)."""
import os, glob, hashlib
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents import SearchClient
from azure.search.documents.indexes.models import (
    SearchIndex, SearchField, SearchFieldDataType, SimpleField, SearchableField,
    VectorSearch, HnswAlgorithmConfiguration, VectorSearchProfile,
    SemanticConfiguration, SemanticPrioritizedFields, SemanticField, SemanticSearch,
)
from azure.ai.projects import AIProjectClient

load_dotenv()
ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
INDEX = os.environ["AZURE_SEARCH_INDEX"]
EMBED_DEPLOYMENT = os.environ.get("AZURE_EMBED_DEPLOYMENT_NAME", "embed")
CRED = DefaultAzureCredential()

# --- Azure OpenAI client for embeddings ---
# IMPORTANT: embeddings route to the ACCOUNT (base) endpoint, NOT the /api/projects/... project endpoint.
# Using the project endpoint here returns HTTP 404 on /embeddings. Use AzureOpenAI with an explicit
# api_version (this is the pattern verified to work; get_openai_client() routing has been unreliable).
from openai import AzureOpenAI
from azure.identity import get_bearer_token_provider

_token_provider = get_bearer_token_provider(CRED, "https://cognitiveservices.azure.com/.default")
openai_client = AzureOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],   # https://<account>.cognitiveservices.azure.com/
    azure_ad_token_provider=_token_provider,
    api_version="2024-10-21",
)

def chunk(text: str, target=800, overlap=150):
    """Paragraph-aware chunking with overlap. Simple > clever; explain trade-offs in your ADR."""
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

def create_index():
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

def run():
    create_index()
    sc = SearchClient(ENDPOINT, INDEX, CRED)
    docs = []
    for path in glob.glob("data/policies/*.md"):
        text = open(path, encoding="utf-8").read()
        for i, ch in enumerate(chunk(text)):
            docs.append({"id": hashlib.md5(f"{path}-{i}".encode()).hexdigest(),
                         "content": ch, "source": os.path.basename(path)})
    vectors = embed([d["content"] for d in docs])
    for d, v in zip(docs, vectors):
        d["vector"] = v
    sc.upload_documents(docs)
    print(f"Indexed {len(docs)} chunks into '{INDEX}'")

if __name__ == "__main__":
    run()