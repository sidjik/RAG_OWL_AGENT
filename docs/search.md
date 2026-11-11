# Retrieval, Qdrant and HyDE

## Ontology entities

The index contains named subjects of the RDF graph. Each document includes the
IRI local name, rdfs:label, skos:prefLabel / altLabel, rdfs:comment, skos:definition
and DC/DCTerms description. Language tags are retained in the underlying triples.
Named objects without outgoing triples are not currently included in this index.

Tokenization extracts Unicode words, applies case folding and adds CamelCase
components: VectorDatabase → vectordatabase, vector, database. It performs neither
translation nor morphological analysis. Queries receive the same processing;
CamelCase boundaries cannot be recovered from a word already supplied in lowercase.

BM25 uses rank-bm25 BM25Plus with k1=1.2, b=0.75 and delta=0.
A zero delta removes the baseline score for documents without matching terms;
positive IDF is useful for small ontologies. An exact full IRI match adds 8;
a case-insensitive exact local-name or label match adds 4, as a single bonus.

In hybrid mode, Qdrant retrieves cosine neighbors within the same ontology and
version, applying the category filter before ranking. Up to 50 candidates from
each channel are combined through RRF: sum of 1/(60 + rank), with rank starting at 1.
The final hybrid score is RRF plus the exact-match bonus. BM25 and cosine scores
are returned separately in scores; their raw values are not added together.
Non-positive cosine matches are discarded. Ties in the final score are broken
by full IRI. Hybrid candidate counts are bounded; `total` refers to the returned
candidate list, not every possible neighbor in the graph.

Embeddings are produced by a LiteLLM or Sentence Transformers adapter, normalized
and stored in Qdrant. Empty vectors, zero vectors, non-finite values and incompatible
dimensions are rejected. Different model identifiers use different collections.
If the upstream model behind an alias changes, change the alias / model_id and
rebuild the index, even when the vector dimensions remain the same.

## Graph context

Search results provide seed entities. BFS follows outgoing and/or incoming edges,
including BNode resources, while preserving their identity as blank nodes. Triples
retain their orientation and term types. Deduplication and cycle protection keep
the queue bounded. Depth and count budgets are described in the
[MCP contract](mcp-tools.md). Traversal does not perform logical inference.

## External documents and HyDE

Knowledge MCP stores external documents separately from ontology entities.
Vector queries require a workspace and accept an optional source_type filter.
A search score represents similarity, not the reliability of an assertion.

HyDE follows this sequence:

```text
question → LLM → hypothetical passage → encoder → Qdrant → actual stored passages
```

The hypothesis is not indexed and is returned with hypothesis_is_evidence=false.
The current implementation uses one hypothetical document, without averaging
multiple generations. Improved accuracy is not assumed: vector / hybrid / HyDE
retrieval still needs comparison on an evaluation question set.
Method: [Gao et al., ACL 2023](https://aclanthology.org/2023.acl-long.99/).

Web search calls Tavily with include_answer=false and include_raw_content=text.
Extracted text is capped at 60,000 characters with an explicit truncation flag,
then split into chunks of up to 1200 characters with overlap of up to 150 characters.
URLs are canonicalized without fragments, and duplicates within one response are
skipped. URL + workspace + chunk_index produce a stable ID. Updates overwrite
chunks and remove any surplus chunks from the previous version. Replacement is
not a document-wide transaction and does not yet support multiple concurrent writers.
The stored SHA-256 covers the indexed text, not the original HTML bytes.
