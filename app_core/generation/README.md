# Generation Layer

Responsible for:

- prompt construction from user query and retrieved context;
- grounded answer generation based only on provided context;
- insufficient-basis behavior when documents are not enough for a supported
  conclusion;
- source-aware answer requirements (citations/attribution from retrieved
  metadata);
- language preservation (respond in the user's language);
- explicit separation between facts from retrieved context and cautious
  conclusions.

Implemented in `prompts.py` (prompt construction) and `answer_generator.py`
(hosted chat model calls), and used by `rag_pipeline.py`.

Core generation prompt logic stays domain-agnostic; domain-specific prompt
content belongs in vertical configuration/example layers, not here.
