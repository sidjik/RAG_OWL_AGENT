# MCP-инструменты Python-версии

## OWL MCP

Запуск: `uv run owl-mcp --ontology demo=examples/ontologies/minimal.owl`.
По умолчанию stdio, stdout содержит только протокол. Для HTTP добавьте
`--transport streamable-http --port 8001`; endpoint `/mcp`.
`--ontology ID=PATH` можно повторять. Реестр фиксируется при запуске.

| Tool | Вход | Результат |
| --- | --- | --- |
| `list_ontologies` | нет | Источники, ontology_id, версии и число троек |
| `list_classes` | ontology_id, offset=0, limit=100 | Страница полных IRI явных owl:Class |
| `get_entity` | ontology_id, iri | Карточка именованного субъекта с прямыми родителями/детьми |
| `get_relations` | ontology_id, node, direction=outgoing, offset=0, limit=100 | Исходные тройки; node — полный IRI или _: метка |
| `search_entities` | ontology_id, query, kind=all, mode=lexical, offset=0, limit=20 | Совпадения, оценки каналов, RDF-подтверждения |
| `retrieve_context` | ontology_id, query, kind=all, mode=lexical и бюджеты | Seeds, узлы и тройки контекста, причины усечения |

`kind`: all / class / property / individual / ontology / other.
`mode`: lexical / hybrid; hybrid требует embeddings и Qdrant.
`direction`: outgoing / incoming / both.
Для страниц `limit` 1–500, `offset >= 0`. Возвращаются `items`, `total`,
`offset`, `limit`, `next_offset` (null в конце). Иерархия карточки не пагинируется;
для больших графов получайте тройки через `get_relations`.

Бюджеты `retrieve_context`: seed_limit=3 (1–10), max_depth=2 (0–4),
max_nodes=50 (1–200), max_statements=100 (1–500), direction=both.
Все выбранные seed-узлы должны помещаться в max_nodes.

Все результаты конкретной онтологии включают `source`: ontology_id, version
(SHA-256), document (file URI), format, triple_count, semantics=asserted.
В тройке есть subject, predicate (полный IRI) и object. У терма — kind,
value, n3, datatype и language. Пустые языки/типы представлены null.

Пример входа:

```json
{"ontology_id":"demo","query":"Computer","seed_limit":1,"max_depth":2,"max_statements":30}
```

Неверные параметры и неизвестная онтология возвращают MCP tool error.
Нулевые результаты поиска — успешный ответ с пустым списком.
`get_relations` для отсутствующего узла также возвращает пустую страницу.

## Knowledge MCP

Запуск: `uv run knowledge-mcp --transport streamable-http --port 8002`.
Требует EMBEDDING_MODEL и доступный Qdrant. Endpoint `/mcp`.

| Tool | Вход | Побочный эффект |
| --- | --- | --- |
| `search_knowledge` | query, workspace=default, limit=10, source_type=all | Нет |
| `hyde_search` | query, workspace=default, limit=10, source_type=all | Вызов LLM; в Qdrant не пишет |
| `web_search_and_index` | query, workspace=default, max_results=5 | Поиск в интернете и запись извлечённых страниц в Qdrant |

`source_type`: all / web / pdf. PDF-фильтр предусмотрен, загрузчик PDF пока в плане.
`limit`: 1–100, `max_results`: 1–10. `workspace`: 1–64 латинские буквы,
цифры, `_` или `-`. Это фильтр, а не система прав доступа.

HyDE возвращает `hypothesis`, `hypothesis_is_evidence=false` и `hits` из реальной
базы документов. Требует HYDE_MODEL. Ссылаться можно на hits, не на hypothesis.
Web-search требует TAVILY_API_KEY. Поисковые сниппеты показываются для ориентации,
но индексируется только raw_content страницы. Пропуски отражаются в status/reason.

Внешние фрагменты содержат URL, version, retrieved_at, document_id, chunk_index,
source_type и trust=external_unverified. Текст внешнего документа не является
инструкцией агенту или аксиомой OWL. Web-инструмент объявлен с readOnlyHint=false.
