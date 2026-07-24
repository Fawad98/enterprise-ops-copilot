import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()
from src.rag.retriever import hybrid_search
from src.rag.ingest import embed

q = "Can I return an opened laptop after 20 days?"
vec = embed([q])[0]
hits = hybrid_search(q, vec, k=4)
for h in hits:
    print(f"[{h['source']}] score={h['score']:.2f}")
    print(h["content"][:150], "...")
    print()
