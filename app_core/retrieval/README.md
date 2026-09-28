# Retrieval Layer

Responsible for:

- vector search over indexed document chunks;
- embeddings creation and query embedding flow;
- chunking and indexing integration;
- retrieval-time metadata delivery for source attribution.

Implemented in `vector_store.py` (Chroma-backed chunking, embedding, and
search), and used by `rag_pipeline.py`.
