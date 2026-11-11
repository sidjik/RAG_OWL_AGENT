# Как читать Python-реализацию

1. `src/owl_rag/ontology.py`: файл превращается в RDFLib Graph; IRI,
   BNode и Literal остаются разными типами. Посмотрите `Ontology.load`,
   `parents`, `children` и соответствующие тесты `tests/test_ontology.py`.
2. `models.py`: RDF-термы преобразуются в JSON без потери языка и datatype.
3. `search.py`: именованные субъекты превращаются в документы для BM25,
   затем результаты могут объединяться с Qdrant через RRF.
4. `vector_store.py`: encoder создаёт векторы, Qdrant хранит их с метаданными;
   обязательный scope ограничивает выборку.
5. `context.py`: очередь BFS, защита от циклов, глубина и бюджеты.
6. `service.py`: выбирает конкретную онтологию и возвращает результаты с source.
7. `cli.py` и `mcp_server.py`: два адаптера одних операций — локальный CLI и MCP.
8. `knowledge.py`: отдельно устроены внешние документы. `hyde_search` только
   читает индекс, `web_search_and_index` явно пополняет его.
9. `providers.py`, `web_search.py`: сетевые вызовы находятся за небольшими
   заменяемыми интерфейсами. В тестах реальные платные API не нужны.

Начните с `uv run owl-inspect examples/ontologies/minimal.owl --entity Computer`.
Затем найдите, как этот вызов проходит через CLI и сервис до RDFLib.

`Protocol` описывает ожидаемые методы адаптера, `dataclass` хранит данные,
Pydantic проверяет параметры и JSON-модели. `URIRef` нельзя заменять простым
коротким именем: одинаковые имена допустимы в разных пространствах IRI.
