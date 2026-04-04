# Vector Search Options for HMRC Tax MCP

This document captures the design decisions and options evaluated for adding
vector search / RAG (Retrieval-Augmented Generation) capabilities to the
HMRC Tax MCP server.

---

## What is Vector Search?

Traditional search matches **exact keywords**. Vector search matches **meaning**.

Every piece of text can be converted into a list of numbers (a **vector** or
**embedding**) that captures its semantic meaning. Similar meanings produce
similar vectors, so the search engine finds documents whose vectors are
**closest** to the query vector — typically measured by cosine similarity.

```
"pension annual allowance"          → [0.12, -0.45, 0.78, ...]  # 1536 numbers
"how much can I pay into a pension?" → [0.11, -0.43, 0.81, ...]  # very similar
"cat food recipes"                  → [0.89, 0.23, -0.11, ...]  # completely different
```

### Why it Matters for This App

HMRC guidance uses formal legal language; users ask questions in plain English.
A user might ask *"Can I still contribute to my SIPP after taking income
drawdown?"* — keyword search misses this, vector search finds the relevant
section about pension flexibility after crystallisation.

### End-to-End Flow

```
INDEXING (offline, run periodically):
  HMRC text → Azure OpenAI (text-embedding-3-small) → 1536-dim vector → stored in DB

QUERYING (runtime, per request):
  User question → Azure OpenAI (same model) → query vector
       ↓
  "Find the 5 stored vectors closest to this one"
       ↓
  Return the original HMRC text chunks those vectors represent
       ↓
  Feed chunks + question to GPT-4o-mini → cited answer
```

This pattern — retrieve relevant chunks then generate an answer — is **RAG**.

### Why Not Ask GPT Directly?

GPT's training data has a cut-off and doesn't cover every HMRC manual section.
RAG provides:
- **Current** HMRC guidance (updated when you re-index)
- **Cited sources** (PTM063300, IHTM17000, etc.)
- **Smaller, cheaper model** usage — GPT-4o-mini works because you're supplying
  the relevant context rather than expecting the model to recall it

---

## How the AST/DSL Links to Vectors

The `rule_id` field is the join key between the rule engine and the vector index.

Every rule YAML already contains `citations` pointing to HMRC manual sections:

```yaml
# src/hmrc_tax_mcp/registry/rules/2025-26/pension_annual_allowance.yaml
rule_id: pension_annual_allowance
citations:
  - label: PTM063300
    url: https://www.gov.uk/hmrc-internal-manuals/pensions-tax-manual/ptm063300
```

At index time, `scripts/indexing/tag_rules.py` auto-generates `citation_map.json`:

```json
{
  "PTM063300": ["pension_annual_allowance", "tapered_annual_allowance"],
  "PTM063500": ["carry_forward"],
  "IHTM17000": ["iht_nil_rate_band", "rnrb"]
}
```

Each HMRC chunk is tagged with all `rule_id`s that cite its manual section:

```json
{
  "id": "ptm063300-chunk-0",
  "manual_ref": "PTM063300",
  "rule_ids": ["pension_annual_allowance", "tapered_annual_allowance"],
  "text": "The annual allowance is reduced...",
  "embedding": [0.12, -0.45, ...]
}
```

### What the AST/DSL Contributes vs. Vectors

| Capability | AST/DSL rule engine | Vector search |
|---|---|---|
| Precise statutory calculation | ✅ | ❌ |
| Human-readable explanation | ❌ | ✅ |
| HMRC citations | ✅ (in YAML) | ✅ (from chunks) |
| Natural language understanding | ❌ | ✅ |

They are complementary — vectors never calculate, the rule engine never explains.

### Runtime Data Flow

```
User query
    │
    ├─► MCP: execute_rule()          ──────────────────► precise numeric result
    │                                                              │
    └─► MCP: search_hmrc_guidance()  ──► relevant HMRC chunks     │
              (filtered by rule_id)                                │
                         │                                         │
                         └──────────────► GPT-4o-mini ◄───────────┘
                                                │
                                          Cited answer
```

Both MCP tool calls run **in parallel** — the rule engine and vector search are
independent. GPT synthesises both outputs into one cited response.

### Integration Patterns

**Pattern A — Rule executes → fetch explanation:**
```
1. execute_rule("pension_annual_allowance", {adjusted_net_income: 80000})
   → result: £50,000

2. vector_search(query="pension annual allowance",
                 filter="rule_id = pension_annual_allowance")
   → PTM063300 chunk: "The annual allowance is reduced by £1 for every £2..."

3. GPT-4o-mini(result + chunk + question)
   → "Your annual allowance is £50,000. HMRC taper rules (PTM063300)..."
```

**Pattern B — Natural language → rule discovery → execute:**
```
1. vector_search("contributing to pension after retirement")
   → top chunks tagged: rule_ids: ["mpaa", "pension_input_amount"]

2. execute_rule("mpaa", {has_triggered_mpaa: true})
   → result: £10,000

3. GPT-4o-mini(result + chunks + question)
   → "Once you've flexibly accessed your pension, your allowance drops to £10,000..."
```

---

## Option Comparison: Vector Search Backends

### Index Size Estimate for HMRC Content

| Content | Chunks | Text storage | Vector storage (1536-dim × float32) |
|---|---|---|---|
| PTM + IHTM + CG + PIM (~4,700 manual sections) | ~14,100 | ~28MB | ~85MB |
| Index overhead (inverted index, HNSW graph) | — | ~3MB | ~3MB |
| **Total** | **~14,100 chunks** | | **~116MB** |

This is a small index — comfortably fits in any of the options below.

---

### Option 1: Azure AI Search (Standard S1)

**Reference:** `docs/architecture/ai-search-integration.md`

| Property | Value |
|---|---|
| Storage | Managed SSD inside the Search service (Microsoft-operated) |
| Capacity (S1) | 25GB per partition |
| Hybrid search | ✅ keyword + vector in one query |
| Semantic re-ranker | ✅ included in Standard tiers |
| Region data residency | ✅ stays in chosen region (UK South) |
| Complexity | Low — fully managed PaaS |
| **Monthly cost (S1, 1 replica)** | **~£250/month** |

**Best for:** Production workloads where semantic re-ranking quality matters and
ops overhead must be minimal.

**Drawback:** Most expensive option by a significant margin.

---

### Option 2: Cosmos DB for NoSQL — Built-in Vector Search ⭐ Recommended for MVP

Cosmos DB (which the app already uses) supports **DiskANN vector indexing**
natively. No additional service required.

#### Enabling It

**Step 1 — Enable at account level (one-time):**

```bash
az cosmosdb update \
  --name <your-account> \
  --resource-group <rg> \
  --capabilities EnableNoSQLVectorSearch
```

Or via Azure Portal: **Cosmos DB account → Settings → Features →
"Vector Search for NoSQL API" → Enable**

> ⚠️ Vector policies must be set at **container creation** — they cannot be
> added to an existing container.

**Step 2 — Create a container with a vector policy:**

```python
db.create_container(
    id="hmrc-chunks",
    partition_key={"paths": ["/rule_id"], "kind": "Hash"},
    vector_embedding_policy={
        "vectorEmbeddings": [{
            "path": "/embedding",
            "dataType": "float32",
            "dimensions": 1536,          # text-embedding-3-small
            "distanceFunction": "cosine"
        }]
    },
    indexing_policy={
        "vectorIndexes": [{
            "path": "/embedding",
            "type": "diskANN"            # use "flat" for <10K docs
        }]
    }
)
```

**Step 3 — Insert documents:**

```python
container.upsert_item({
    "id": "ptm063300-chunk-0",
    "rule_id": "pension_annual_allowance",
    "manual_ref": "PTM063300",
    "tax_year": "2025-26",
    "rule_ids": ["pension_annual_allowance", "tapered_annual_allowance"],
    "text": "The annual allowance is £60,000...",
    "embedding": [0.123, -0.456, ...]    # 1536 floats from Azure OpenAI
})
```

**Step 4 — Query:**

```python
query = """
    SELECT TOP 5 c.text, c.rule_ids, c.manual_ref,
                 VectorDistance(c.embedding, @vec) AS score
    FROM c
    WHERE ARRAY_CONTAINS(c.rule_ids, @rule_id)
    ORDER BY VectorDistance(c.embedding, @vec)
"""
results = container.query_items(
    query=query,
    parameters=[
        {"name": "@vec", "value": query_embedding},
        {"name": "@rule_id", "value": "pension_annual_allowance"}
    ],
    enable_cross_partition_query=True
)
```

#### Key Constraints

| Constraint | Detail |
|---|---|
| GA status | GA for NoSQL API; DiskANN is production-ready |
| Container creation only | Cannot add vector policy to existing containers |
| Max dimensions | 4,096 per vector field |
| Max vector fields | 5 per container |
| Semantic re-ranker | ❌ Not available — manual re-ranking via Azure OpenAI if needed |
| RU cost | Vector queries consume more RUs than regular queries |

| Property | Value |
|---|---|
| **Monthly cost** | **~£10–20 extra on existing Cosmos DB bill** |
| **Best for** | MVP / early production — zero extra infrastructure |

---

### Option 3: PostgreSQL + pgvector

If the app migrates from Cosmos DB to Azure Database for PostgreSQL, the
`pgvector` extension adds vector search to the same database.

```sql
-- Enable extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create chunks table
CREATE TABLE hmrc_chunks (
    id          TEXT PRIMARY KEY,
    rule_ids    TEXT[],
    manual_ref  TEXT,
    tax_year    TEXT,
    text        TEXT,
    embedding   vector(1536)
);

-- Create HNSW index
CREATE INDEX ON hmrc_chunks USING hnsw (embedding vector_cosine_ops);

-- Hybrid query: keyword filter + vector similarity
SELECT text, rule_ids, manual_ref,
       1 - (embedding <=> $1::vector) AS score
FROM hmrc_chunks
WHERE rule_ids @> ARRAY['pension_annual_allowance']
ORDER BY embedding <=> $1::vector
LIMIT 5;
```

| Property | Value |
|---|---|
| Semantic re-ranker | ❌ Manual re-ranking via Azure OpenAI |
| Hybrid search | ✅ BM25 keyword + HNSW vector |
| **Monthly cost** | **~£0–50 extra on existing Postgres instance** |
| **Best for** | Apps already on PostgreSQL; lowest cost option |

---

### Option 4: Qdrant (self-hosted on ACA)

Purpose-built Rust vector database. Run as a container alongside the MCP server.

```python
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, Filter, FieldCondition

client = QdrantClient(url="http://qdrant:6333")

# Create collection
client.create_collection("hmrc-chunks", vectors_config=VectorParams(
    size=1536, distance=Distance.COSINE
))

# Search with metadata filter
results = client.search(
    collection_name="hmrc-chunks",
    query_vector=query_embedding,
    query_filter=Filter(must=[
        FieldCondition(key="rule_id", match={"value": "pension_annual_allowance"})
    ]),
    limit=5
)
```

| Property | Value |
|---|---|
| Semantic re-ranker | ❌ |
| Hybrid search | ✅ BM25 + vector |
| **Monthly cost (ACA container)** | **~£15–30/month** |
| **Best for** | Pure vector performance; no Cosmos/Postgres dependency |

---

### Option 5: Weaviate (self-hosted on ACA)

Similar to Qdrant but with GraphQL API, multi-modal support, and built-in
BM25+vector hybrid.

| Property | Value |
|---|---|
| **Monthly cost (ACA container)** | **~£15–40/month** |
| **Best for** | If multi-modal search (e.g. pension statement images) is a future requirement |

---

## Summary Comparison

| Option | Monthly cost | Hybrid search | Semantic rerank | Azure native | Ops complexity |
|---|---|---|---|---|---|
| **Azure AI Search S1** | ~£250 | ✅ | ✅ | ✅ | Low |
| **Cosmos DB vector** ⭐ | ~£10–20 extra | ✅ (vector + filter) | ❌ | ✅ | Low |
| **PostgreSQL pgvector** | ~£0–50 extra | ✅ | ❌ | ✅ (Azure PG) | Low |
| **Qdrant (self-hosted)** | ~£15–30 | ✅ | ❌ | ❌ | Medium |
| **Weaviate (self-hosted)** | ~£15–40 | ✅ | ❌ | ❌ | Medium |

## Recommendation

| Stage | Recommended option | Reason |
|---|---|---|
| **MVP / development** | Cosmos DB vector | Zero extra infrastructure; already provisioned |
| **Production (budget-sensitive)** | Cosmos DB vector or pgvector | £200+/month saving vs AI Search |
| **Production (quality-first)** | Azure AI Search S1 | Semantic re-ranker gives meaningfully better results for natural language financial queries |
| **Future: multi-modal** | Weaviate | Built-in support for image + text if pension statement upload is added |
