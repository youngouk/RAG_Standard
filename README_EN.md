<p align="center">
  <img src="assets/logo.svg" alt="OneRAG Logo" width="400"/>
</p>

<p align="center">
  <strong>Start in 5 minutes, swap components with 1 line of config - Production-ready RAG Backend</strong>
</p>

<p align="center">
  <a href="https://github.com/youngouk/OneRAG/actions/workflows/ci.yml"><img src="https://github.com/youngouk/OneRAG/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="https://github.com/youngouk/OneRAG/stargazers"><img src="https://img.shields.io/github/stars/youngouk/OneRAG?style=social" alt="GitHub Stars"></a>
</p>

<p align="center">
  <a href="README.md">한국어</a> | <strong>English</strong>
</p>

---

## TL;DR

```bash
git clone https://github.com/youngouk/OneRAG.git && cd OneRAG && uv sync
```

```bash
# 🐳 Have Docker → Full API Server (Weaviate + FastAPI + Swagger UI)
cp quickstart/.env.quickstart .env   # Set only GOOGLE_API_KEY
make start                            # → http://localhost:8000/docs

# 💻 No Docker → Local CLI Chatbot (runs instantly)
make easy-start                       # → Chat directly in terminal
```

**Want to change Vector DB?** Change 1 line in `.env`: `VECTOR_DB_PROVIDER=pinecone`
**Want to change LLM?** Change 1 line: `LLM_PROVIDER=openai`. Done.

---

## Why OneRAG?

### Problems with Traditional RAG Development

| Situation | Traditional Approach | OneRAG |
|-----------|---------------------|--------|
| Change Vector DB | Rewrite entire codebase + test repeatedly | Change 1 line in `.env` |
| Switch LLM | Rewrite API integration code | Change 1 line in `.env` |
| Add features (caching, reranking, etc.) | Implement from scratch | Toggle On/Off in `YAML` |
| PoC → Production | Rebuild from scratch | Scale with same codebase |

### What OneRAG Provides

```
┌─────────────────────────────────────────────────────────────────┐
│                         OneRAG                                   │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────┤
│  Vector DB  │     LLM     │  Reranker   │    Cache    │  Extra  │
├─────────────┼─────────────┼─────────────┼─────────────┼─────────┤
│ • Weaviate  │ • Gemini    │ • Jina      │ • Memory    │ • Graph │
│ • Chroma    │ • OpenAI    │ • Cohere    │ • Redis     │   RAG   │
│ • Pinecone  │ • Claude    │ • Google    │ • Semantic  │ • PII   │
│ • Qdrant    │ • OpenRouter│ • OpenAI    │             │   Mask  │
│ • pgvector  │             │ • Local     │             │ • Agent │
│ • MongoDB   │             │             │             │         │
└─────────────┴─────────────┴─────────────┴─────────────┴─────────┘
                    ↑ All swappable via config files
```

---

## Getting Started

Choose the method that fits your environment.

|  | Full API Server (`make start`) | CLI Chatbot (`make easy-start`) |
|---|---|---|
| **Docker** | Required | Not required |
| **Vector DB** | Weaviate (hybrid search) | ChromaDB (local file) |
| **Interface** | REST API + Swagger UI | Terminal CLI |
| **LLM** | 4 providers (Gemini, OpenAI, Claude, OpenRouter) | Gemini / OpenRouter |
| **Use case** | Production, API integration, team dev | Learning, exploration, quick PoC |

### Option A: Full API Server (Docker)

```bash
git clone https://github.com/youngouk/OneRAG.git
cd OneRAG && uv sync

cp quickstart/.env.quickstart .env
# Set GOOGLE_API_KEY in .env file
# (Free: https://aistudio.google.com/apikey)

make start
```

**Done!** Test immediately at [http://localhost:8000/docs](http://localhost:8000/docs)

```bash
make start-down  # Stop
```

### Option B: Local CLI Chatbot (No Docker)

Experience RAG search + AI answers directly in your terminal without Docker.

```bash
git clone https://github.com/youngouk/OneRAG.git
cd OneRAG && uv sync

make easy-start
```

25 sample documents are auto-loaded with hybrid search (Dense + BM25) ready to go.
To enable AI answer generation, set one API key:

```bash
# Set just one of these
export GOOGLE_API_KEY="your-key"       # Free: https://aistudio.google.com/apikey
export OPENROUTER_API_KEY="your-key"   # https://openrouter.ai/keys
```

> **New to OneRAG?** Start with `make easy-start` and ask the chatbot directly.
> "What is hybrid search?", "How does the RAG pipeline work?" — the sample data has the answers.

---

## Swapping Components

### Change Vector DB (1 line)

```bash
# Change just one line in .env
VECTOR_DB_PROVIDER=weaviate  # or chroma, pinecone, qdrant, pgvector, mongodb
```

### Change LLM (1 line)

```bash
# Change just one line in .env
LLM_PROVIDER=google  # or openai, anthropic, openrouter
```

### Add Reranker (2 lines YAML)

```yaml
# app/config/features/reranking.yaml
reranking:
  approach: "cross-encoder"  # or late-interaction, llm, local
  provider: "jina"           # or cohere, google, openai, sentence-transformers
```

### Toggle Features On/Off (YAML config)

```yaml
# Enable caching
cache:
  enabled: true
  type: "redis"  # or memory, semantic

# Enable GraphRAG
graph_rag:
  enabled: true

# Enable PII masking
pii:
  enabled: true
```

---

## Building Blocks

| Category | Options | How to Change |
|----------|---------|---------------|
| **Vector DB** | Weaviate, Chroma, Pinecone, Qdrant, pgvector, MongoDB | 1 env var |
| **LLM** | Google Gemini, OpenAI, Anthropic Claude, OpenRouter | 1 env var |
| **Reranker** | Jina, Cohere, Google, OpenAI, OpenRouter, Local | 2 lines YAML |
| **Cache** | Memory, Redis, Semantic | 1 line YAML |
| **Query Routing** | LLM-based, Rule-based | 1 line YAML |
| **Korean Search** | Synonyms, stopwords, user dictionary | YAML config |
| **Security** | PII detection, masking, audit logging | YAML config |
| **GraphRAG** | Knowledge graph-based relation reasoning | 1 line YAML |
| **Agent** | Tool execution, MCP protocol | YAML config |

---

## RAG Pipeline

```
Query → Router → Expansion → Retriever → Cache → Reranker → Generator → PII Masking → Response
```

| Stage | Function | Swappable |
|-------|----------|-----------|
| Query Routing | Classify query type | LLM/Rule selection |
| Query Expansion | Synonyms, stopwords | Custom dictionary |
| Retrieval | Vector/hybrid search | 6 DBs |
| Caching | Response cache | 3 cache types |
| Reranking | Sort search results | 6 rerankers |
| Generation | LLM response | 4 LLMs |
| Post-processing | PII masking | Custom policies |

---

## Configuration Guide by Stage

| Stage | Components | Use Case |
|-------|------------|----------|
| **Basic** | Vector search + LLM | Simple document Q&A |
| **Standard** | + Hybrid search + Reranker | Services requiring search quality **(Recommended)** |
| **Advanced** | + GraphRAG + Agent | Complex relation reasoning, tool execution |

> Start with Basic, add blocks as needed.

---

## Development

```bash
make dev-reload   # Dev server (auto-reload)
make test         # Run tests
make lint         # Lint check
make type-check   # Type check
```

---

## Documentation

- [Detailed Setup Guide](docs/SETUP.md)
- [Architecture Overview](docs/TECHNICAL_DEBT_ANALYSIS.md)
- [Streaming API Guide](docs/streaming-api-guide.md)
- [WebSocket API Guide](docs/websocket-api-guide.md)

---

## License

MIT License

---

<p align="center">
  <sub>This project was created by a RAG Chat Service PM who wanted to implement features accumulated across multiple projects.<br>
  Designed so that beginners can easily run PoCs and scale to production.</sub>
</p>

<p align="center">
  <a href="https://github.com/youngouk/OneRAG/issues">Report Bug</a> ·
  <a href="https://github.com/youngouk/OneRAG/issues">Request Feature</a> ·
  <a href="https://github.com/youngouk/OneRAG/discussions">Discussions</a>
</p>
