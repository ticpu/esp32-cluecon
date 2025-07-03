# Troubleshooting Guide

## "Illegal instruction" Error

### Problem
When running `sw-search` with embedding generation, you may encounter an "Illegal instruction" error that crashes the process.

### Root Cause
This error occurs when PyTorch was compiled with newer CPU instruction sets (like AVX2 or AVX-512) that aren't supported by your CPU. This is common on older server hardware.

### Diagnosis
1. **Check your CPU capabilities:**
   ```bash
   cat /proc/cpuinfo | grep -E "(model name|flags)" | head -5
   ```

2. **Check PyTorch version:**
   ```bash
   python -c "import torch; print('PyTorch version:', torch.__version__)"
   ```

3. **Test model loading:**
   ```bash
   python -c "from sentence_transformers import SentenceTransformer; model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')"
   ```

### Solution
Set environment variables to disable unsupported instruction sets:

```bash
export PYTORCH_DISABLE_AVX2=1
export PYTORCH_DISABLE_AVX512=1
```

Then run your commands:
```bash
PYTORCH_DISABLE_AVX2=1 PYTORCH_DISABLE_AVX512=1 sw-search ./docs --output index.swsearch
```

### Permanent Fix
Add these to your shell profile (`.bashrc`, `.zshrc`, etc.):
```bash
export PYTORCH_DISABLE_AVX2=1
export PYTORCH_DISABLE_AVX512=1
```

## Chunking Strategy Guide

The `sw-search` tool supports four different chunking strategies, each with different trade-offs:

### 1. Sentence-based Chunking (Default)
**Best for:** Most use cases, balanced content quality

```bash
sw-search ./docs --chunking-strategy sentence --max-sentences-per-chunk 8
```

**Characteristics:**
- Groups content by sentences for natural boundaries
- Default: 8 sentences per chunk
- Good balance of context and searchability
- Respects sentence boundaries for readability

**Results:** Medium-sized chunks with complete thoughts and good context.

### 2. Sliding Window Chunking
**Best for:** Dense content, overlapping context needed

```bash
sw-search ./docs --chunking-strategy sliding --chunk-size 100 --overlap-size 20
```

**Characteristics:**
- Word-based chunks with overlap
- Default: 100 words per chunk, 20 words overlap
- Ensures no information is lost at boundaries
- More chunks but better coverage

**Results:** Smaller, overlapping chunks that capture all content nuances.

### 3. Paragraph-based Chunking
**Best for:** Well-structured documents with clear paragraph breaks

```bash
sw-search ./docs --chunking-strategy paragraph
```

**Characteristics:**
- Splits on double newlines (paragraph boundaries)
- Chunk size varies based on paragraph length
- Preserves document structure
- Can create very small or very large chunks

**Results:** Variable-sized chunks that respect document structure.

### 4. Page-based Chunking
**Best for:** PDFs, presentations, or documents with page boundaries

```bash
sw-search ./docs --chunking-strategy page
```

**Characteristics:**
- Splits on page boundaries or form feeds
- For text files, creates roughly equal-sized pages
- Good for documents with natural page breaks
- Preserves page-level context

**Results:** Page-sized chunks that maintain document flow.

### Choosing the Right Strategy

| Use Case | Recommended Strategy | Reason |
|----------|---------------------|---------|
| General documentation | `sentence` | Balanced, readable chunks |
| Technical manuals | `sliding` | Overlapping context prevents information loss |
| Blog posts/articles | `paragraph` | Respects natural structure |
| PDFs/presentations | `page` | Maintains original pagination |
| Code documentation | `sentence` with `--split-newlines 2` | Respects code blocks |

### Quality Comparison

Based on search results for "how to deploy agents":

- **Sentence chunking:** Provides substantial, readable content with good context
- **Sliding window:** Captures more detail but may have fragmented text
- **Paragraph chunking:** Can create very small chunks (just headers) or very large ones
- **Page chunking:** Good for maintaining document flow but may split related content

### Recommendations

1. **Start with sentence chunking** (default) for most use cases
2. **Use sliding window** if you need comprehensive coverage and don't mind more chunks
3. **Use paragraph chunking** only for well-structured documents with consistent paragraph sizes
4. **Use page chunking** for PDFs or when document structure is important

### Advanced Configuration

```bash
# Fine-tuned sentence chunking
sw-search ./docs \
  --chunking-strategy sentence \
  --max-sentences-per-chunk 30 \
  --split-newlines 2

# Optimized sliding window
sw-search ./docs \
  --chunking-strategy sliding \
  --chunk-size 150 \
  --overlap-size 30

# Combined with other options
sw-search ./docs \
  --chunking-strategy sentence \
  --max-sentences-per-chunk 40 \
  --file-types md,txt,rst,py \
  --exclude "**/test/**" \
  --verbose
```

## PostgreSQL pgvector Troubleshooting

### "vector type not found in the database" Error

#### Problem
When using pgvector backend, you may encounter this error during index creation or search.

#### Root Cause
The pgvector extension is not installed or enabled in your PostgreSQL database.

#### Solution
1. **Install pgvector extension (if not already installed):**
   ```bash
   # For PostgreSQL 16
   sudo apt-get install postgresql-16-pgvector
   # Or for other versions, adjust accordingly
   ```

2. **Enable the extension in your database:**
   ```sql
   -- Connect to your database
   psql -U your_user -d your_database
   
   -- Create the extension
   CREATE EXTENSION vector;
   
   -- Verify it's installed
   \dx
   ```

3. **Using Docker? The pgvector/pgvector image includes it pre-installed:**
   ```bash
   docker run -d \
     --name postgres-pgvector \
     -e POSTGRES_USER=signalwire \
     -e POSTGRES_PASSWORD=signalwire123 \
     -e POSTGRES_DB=knowledge \
     -p 5432:5432 \
     pgvector/pgvector:pg16
   ```

### Connection Issues

#### Problem
Cannot connect to PostgreSQL when using pgvector backend.

#### Common Causes and Solutions

1. **PostgreSQL not running:**
   ```bash
   # Check if PostgreSQL is running
   sudo systemctl status postgresql
   
   # Start if needed
   sudo systemctl start postgresql
   ```

2. **Wrong connection string:**
   ```bash
   # Correct format
   postgresql://username:password@host:port/database
   
   # Examples:
   postgresql://signalwire:signalwire123@localhost:5432/knowledge
   postgresql://user:pass@192.168.1.100:5432/mydb
   ```

3. **Authentication failed:**
   - Check username/password
   - Verify pg_hba.conf allows your connection method
   - For local connections, you might need to use `trust` or `md5` authentication

4. **Database doesn't exist:**
   ```sql
   -- Create the database
   createdb -U postgres knowledge
   ```

### Performance Issues

#### Slow Similarity Search

1. **Create proper indexes:**
   ```sql
   -- For small datasets (< 100k rows)
   CREATE INDEX ON your_collection USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
   
   -- For larger datasets
   CREATE INDEX ON your_collection USING ivfflat (embedding vector_cosine_ops) WITH (lists = 1000);
   ```

2. **Tune PostgreSQL for vector operations:**
   ```sql
   -- Increase work_mem for better performance
   SET work_mem = '256MB';
   
   -- For session or globally in postgresql.conf
   ALTER SYSTEM SET work_mem = '256MB';
   ```

3. **Monitor query performance:**
   ```sql
   EXPLAIN (ANALYZE, BUFFERS) 
   SELECT * FROM your_collection 
   ORDER BY embedding <=> '[...]'::vector 
   LIMIT 5;
   ```

### Migration from SQLite to pgvector

#### Steps to Migrate

1. **Export from SQLite:**
   ```python
   from signalwire_agents.search import SearchEngine
   import json
   
   # Load SQLite index
   engine = SearchEngine("docs.swsearch")
   
   # Export chunks (you'll need to implement this export functionality)
   # This is a conceptual example
   chunks = engine.export_all_chunks()
   with open("chunks.json", "w") as f:
       json.dump(chunks, f)
   ```

2. **Import to pgvector:**
   ```bash
   # Rebuild index with pgvector backend
   sw-search ./docs \
     --backend pgvector \
     --connection-string "postgresql://user:pass@localhost/db" \
     --output docs_collection
   ```

### Multi-Agent Deployment Issues

#### Connection Pool Exhaustion

When multiple agents connect to the same pgvector database:

1. **Use connection pooling:**
   ```python
   # Install pgbouncer for connection pooling
   sudo apt-get install pgbouncer
   ```

2. **Configure pgbouncer:**
   ```ini
   # /etc/pgbouncer/pgbouncer.ini
   [databases]
   knowledge = host=localhost port=5432 dbname=knowledge
   
   [pgbouncer]
   pool_mode = transaction
   max_client_conn = 1000
   default_pool_size = 25
   ```

3. **Update connection string:**
   ```bash
   # Connect through pgbouncer (default port 6432)
   postgresql://user:pass@localhost:6432/knowledge
   ```

### Docker-Specific Issues

#### Container Can't Connect to Host PostgreSQL

1. **Use host networking (Linux only):**
   ```bash
   docker run --network host ...
   ```

2. **Or use host.docker.internal (Mac/Windows):**
   ```bash
   postgresql://user:pass@host.docker.internal:5432/knowledge
   ```

3. **Or use Docker network:**
   ```bash
   # Create network
   docker network create myapp
   
   # Run PostgreSQL
   docker run -d --name postgres --network myapp pgvector/pgvector:pg16
   
   # Run your app
   docker run --network myapp -e DB_HOST=postgres ...
   ``` 