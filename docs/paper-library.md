# PDF paper library plan

**Status: a separate upcoming component. The PDF parser, paper index and PDF search
tools are not implemented yet; the initial bibliography is listed below.**

The goal is to let the agent explain AI methods that appear in an ontology or are
used in this project: find a paper, retrieve a relevant passage and cite the document
and page.

## Two types of sources

- **Ontologies** support explicitly asserted classes, relationships and axioms.
- **Papers** describe algorithms, assumptions, experiments and method limitations.
  A statement in a paper does not become an ontology axiom.

The agent will be able to find a method in the ontology and then search publications
to explain how it works. Answers should make clear which parts are supported by the
ontology and which by a paper.

## Initial reading list

Years correspond to the first arXiv version. ArXiv links pin specific publication
versions so the future index and page references can be reproduced.

| Publication | Relevance |
| --- | --- |
| [Lewis et al., Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks, 2020, v4](https://arxiv.org/abs/2005.11401v4) | Basic retrieval-augmented generation architecture |
| [Yao et al., ReAct: Synergizing Reasoning and Acting in Language Models, 2022, v3](https://arxiv.org/abs/2210.03629v3) | Alternating model reasoning and actions through external tools |
| [Edge et al., From Local to Global: A Graph RAG Approach to Query-Focused Summarization, 2024, v2](https://arxiv.org/abs/2404.16130v2) | Graph indexing of a text corpus and answers to global questions |
| [Vaswani et al., Attention Is All You Need, 2017, v7](https://arxiv.org/abs/1706.03762v7) | Transformers and the attention mechanism |
| [Reimers and Gurevych, Sentence-BERT, 2019, v1](https://arxiv.org/abs/1908.10084v1) | Sentence embeddings and similarity retrieval |
| [Malkov and Yashunin, Efficient and robust approximate nearest neighbor search using Hierarchical Navigable Small World graphs, 2016, v4](https://arxiv.org/abs/1603.09320v4) | HNSW for approximate nearest-neighbor vector search |
| [Gao et al., Precise Zero-Shot Dense Retrieval without Relevance Labels, 2022 / ACL 2023](https://aclanthology.org/2023.acl-long.99/) | HyDE: generating a hypothetical document to retrieve actual passages |

Edge et al. extract a graph from text. This OWL GraphRAG project uses an existing
ontology; methods taken from that paper will need a separate applicability evaluation.

## Implementation plan

1. **Document registry:** `document_id`, title, authors, publication version,
   source URL, local path and PDF SHA-256.
2. **Text extraction:** preserve pages and document structure. Start with PDFs
   containing a text layer; OCR for scanned pages and interpretation of images,
   formulas and tables are separate extensions. Report failures to extract text.
3. **Chunks:** split text into passages with `chunk_id`, a document reference,
   page range and position in the extracted text. Use one-based PDF page numbers,
   distinguishing them from page numbers printed in the paper.
4. **Search:** reuse the Qdrant adapter and external-document collection, then
   add BM25 and result fusion for PDFs.
5. **MCP tools:** extend Knowledge MCP. `search_knowledge` and `hyde_search`
   already accept `source_type=pdf`, but PDF ingestion is not implemented yet.
   Add `get_paper_passage` to retrieve a passage with surrounding context.
6. **Agent:** choose between ontology and paper tools, and cite pages and
   publications. A similar method name is not evidence of a connection to a
   specific OWL entity; record such connections separately and explicitly.
7. **Evaluation:** prepare questions with expected passages and pages, then check
   extraction quality, retrieval quality and source accuracy in answers.

Planned flow:

```text
PDF → text per page → chunks with provenance → BM25 / vector index
                                                       ↑
Agent → MCP client → paper search tools ────────────────┘
```

PDF ingestion and paper tools will form a separate component so the general-purpose
OWL server core remains independent of scientific publication formats.
