# RAG_Standard

> A project built by a non-developer PM who wanted to implement features across multiple projects, with the help of vibe coding.
> Created to make RAG accessible to everyone for easy PoC and adoption decisions.

[한국어](README.md) | **English**

[![CI](https://github.com/youngouk/RAG_Standard/actions/workflows/ci.yml/badge.svg)](https://github.com/youngouk/RAG_Standard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## What is this

A modular RAG (Retrieval-Augmented Generation) backend that lets you build **only what you need**.

Designed with DI (Dependency Injection), you can mix and match features from simple vector search to full GraphRAG based on your project scale.

### RAG Pipeline

```
Query → Router → Expansion → Retriever → Cache → Reranker → Generator → PII Masking → Response
```

| Step | Feature | Description |
|------|---------|-------------|
| 1 | Query Routing | LLM/Rule-based query classification |
| 2 | Query Expansion | Synonyms, stopwords, user dictionary |
| 3 | Search | Vector/hybrid search (6 DBs) |
| 4 | Caching | Memory, Redis, semantic cache |
| 5 | Reranking | Cross-Encoder, ColBERT, LLM-based |
| 6 | Response | Multi-LLM support (4 providers) |
| 7 | Post-process | PII detection and masking |

**Optional**: Self-RAG (self-evaluation), GraphRAG (reasoning), Agent (tool execution), SQL Search (metadata)

### DI Container Components

| Category | Components | Description |
|----------|------------|-------------|
| **Core** | LLM Factory, Circuit Breaker | Multi-LLM support, failure isolation |
| **Retrieval** | Retriever, Reranker, Cache | Vector/hybrid search, reranking, semantic cache |
| **BM25 Enhancement** | Synonyms, Stopwords, User Dictionary | Improved Korean search quality |
| **Privacy** | PII Processor, Masker | PII detection and masking |
| **Session** | Session, Memory | Conversation context management |
| **GraphRAG** | Graph Store, Entity Extractor | Knowledge graph-based reasoning |
| **Agent** | Agent Orchestrator, MCP | Agent and tool execution |
| **Storage** | Vector Store, Metadata Store | Vector DB and metadata persistence |

Each category can be enabled/disabled via YAML config, or you can swap implementations.

## Who is this for

- Developers who want to **build their own** RAG system
- Teams that need a **vendor-agnostic** architecture (not locked to specific DB or LLM)
- Projects that want to **scale incrementally** from prototype to production

## Feature Selection Guide

| Level | Components | Use Case |
|-------|------------|----------|
| **Basic** | Vector Search + LLM | Simple document Q&A |
| **Standard** | Hybrid Search (Dense + BM25) + Reranker | Services where search quality matters (recommended) |
| **Advanced** | + GraphRAG + Multi-Query | Complex relationship reasoning |

All components are interface(Protocol)-based, so you can enable only what you need or swap implementations.

## Supported

**Vector DB** (6): Weaviate, Chroma, Pinecone, Qdrant, pgvector, MongoDB

**LLM** (4): Google Gemini, OpenAI, Anthropic Claude, OpenRouter

**Reranker** (6): Jina, Cohere, Google, OpenAI, OpenRouter, Local(sentence-transformers)

## Quickstart

```bash
# 1. Clone & Install
git clone https://github.com/youngouk/RAG_Standard.git
cd RAG_Standard && uv sync

# 2. Configure
cp quickstart/.env.quickstart .env
# Set GOOGLE_API_KEY in .env (Free: https://aistudio.google.com/apikey)

# 3. Run
make quickstart
```

Test the API at http://localhost:8000/docs

```bash
# Stop
make quickstart-down
```

## Development

```bash
make dev-reload    # Dev server (hot reload)
make test          # Run tests
make lint          # Lint check
make type-check    # Type check
```

## Docs

- [Setup Guide](docs/SETUP.md)
- [Architecture](docs/TECHNICAL_DEBT_ANALYSIS.md)
- [Streaming API Guide](docs/streaming-api-guide.md)
- [WebSocket API Guide](docs/websocket-api-guide.md)

## License

MIT License
