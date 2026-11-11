# Запуск инфраструктуры из локального .env

Нужны Docker Engine и Docker Compose 2.20.3+. Основной файл —
[compose.yaml](../compose.yaml) в корне. Старый путь `deploy/compose.yaml`
сохранён как обёртка через `include`.

## Что заполнить

Скопируйте нужные настройки из [.env.example](../.env.example) в свой `.env`.
Если файл уже существует, дополните его; не перезаписывайте имеющиеся ключи.
Пример содержит placeholders: их нужно заменить своими значениями.

| Переменная | Значение |
| --- | --- |
| `LITELLM_MASTER_KEY` | Придуманный вами ключ доступа к локальному прокси, например `sk-` + случайная строка |
| `CHAT_UPSTREAM_MODEL` | Полное имя chat-модели в формате LiteLLM `provider/model-id`; для будущего агента нужна поддержка tools |
| `CHAT_API_KEY` | Ключ провайдера chat-модели; для локального API без авторизации обычно подходит `none` |
| `CHAT_API_BASE` | Свой URL провайдера/совместимого сервера; пусто для стандартного адреса провайдера |
| `EMBEDDING_UPSTREAM_MODEL` | Полное имя embedding-модели в формате LiteLLM `provider/model-id` |
| `EMBEDDING_API_KEY` | Ключ её провайдера; он может совпадать с chat-ключом |
| `EMBEDDING_API_BASE` | Свой embedding endpoint; пусто для стандартного адреса провайдера |
| `TAVILY_API_KEY` | Ключ Tavily; без него сервер запускается, web-search сообщает об отсутствии настройки |
| `ONTOLOGY_PATH` | Путь к файлу относительно корня репозитория или абсолютный путь |
| `ONTOLOGY_ID` | Имя онтологии в MCP, по умолчанию `demo` |
| `ONTOLOGY_FORMAT` | `xml`, `turtle` или `nt`; по умолчанию `xml` |

Upstream-модели задаются только в LiteLLM. В
[конфигурации прокси](../deploy/litellm/config.yaml) определены два публичных имени:

- `chat` → `CHAT_UPSTREAM_MODEL`, используется HyDE и позднее агентом;
- `embeddings` → `EMBEDDING_UPSTREAM_MODEL`, используется индексами и поиском.

Формат `provider/model-id`, `api_key`, `api_base` и ссылки `os.environ/NAME`
описаны в [официальной документации LiteLLM](https://docs.litellm.ai/docs/proxy/configs).
Если выбранный провайдер требует дополнительных параметров, например API version
или credentials-файл, добавьте их в соответствующий блок `litellm_params`.

Для модели, работающей на этом же компьютере, внутри Docker указывайте
`http://host.docker.internal:PORT/v1`. Такой host alias уже настроен у LiteLLM.
Имя `localhost` внутри контейнера обозначает сам контейнер.

## Запуск

Из корня репозитория после заполнения `.env`:

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs --tail=80 litellm owl-mcp knowledge-mcp
```

При отсутствии обязательных `LITELLM_MASTER_KEY`, `CHAT_UPSTREAM_MODEL` или
`EMBEDDING_UPSTREAM_MODEL` Compose покажет, какую переменную нужно заполнить.
`config --quiet` не выводит конфигурацию с ключами.

| Сервис | Адрес с компьютера |
| --- | --- |
| LiteLLM API | `http://localhost:4000/v1` |
| Проверка готовности LiteLLM | `http://localhost:4000/health/readiness` |
| Qdrant | `http://localhost:6333` |
| OWL MCP | `http://localhost:8001/mcp` |
| Knowledge MCP | `http://localhost:8002/mcp` |

Контейнеры MCP используют внутренние адреса `http://litellm:4000/v1` и
`http://qdrant:6333`; Compose подставляет их самостоятельно. Значения
`LITELLM_BASE_URL` и `QDRANT_URL` в примере нужны Python-командам на хосте.
Для локальных Python-команд `LITELLM_API_KEY` по умолчанию берётся из
`LITELLM_MASTER_KEY`. В Compose ключ передаётся явно.

Ключи upstream-провайдеров получает только LiteLLM, ключ Tavily — только
Knowledge MCP. Сервисы MCP получают ключ прокси, а не ключи моделей.
Для локальной разработки используется master key; система пользовательских
virtual keys и управление моделями через БД здесь не настраиваются.

Первое включение OWL MCP создаёт embeddings сущностей выбранной онтологии.
Это вызывает embedding API. При неверном endpoint, модели или ключе посмотрите
логи LiteLLM и OWL MCP. Проверки готовности контейнеров сами модели не вызывают;
здоровый LiteLLM ещё не подтверждает работоспособность upstream-моделей.

LiteLLM запускается без PostgreSQL: модели задаются YAML-файлом, а не Admin UI.
Образ закреплён на официальном [релизе v1.106.6](https://github.com/BerriAI/litellm/releases/tag/v1.106.6).

## Проверка с хоста

```bash
curl --fail http://localhost:4000/health/readiness
uv run --env-file .env owl-inspect examples/ontologies/search.owl \
  --query "vector database" --mode hybrid
```

Вторая команда делает реальные embedding-запросы. MCP endpoint предназначен
для MCP-клиента или Inspector. **Агент и пользовательский чат пока не входят
в этот Compose:** после запуска доступны API прокси и инструменты MCP.

## Обновление настроек и остановка

После смены модели, адреса или ключа перезапустите зависящие от них контейнеры:

```bash
docker compose up -d --force-recreate litellm owl-mcp knowledge-mcp
docker compose down
```

При смене embedding-модели удалите старый индекс или используйте новый
идентификатор vector space. Клиент сейчас идентифицирует encoder по адресу
прокси и alias: замена upstream под прежним `embeddings` требует переиндексации,
даже если размерность та же. OWL индекс строится заново при запуске;
веб-документы нужно загрузить повторно. Автоматическая миграция старых векторов
будет отдельным шагом.

Qdrant сохраняет данные в named volume `qdrant_data` после `docker compose down`.
Для последующих запусков `.env` заново создавать не нужно.
