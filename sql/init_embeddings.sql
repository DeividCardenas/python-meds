CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS medicamentos_embeddings (
    id SERIAL PRIMARY KEY,
    nombre_original TEXT NOT NULL UNIQUE,
    embedding VECTOR(768) NOT NULL
);

CREATE INDEX IF NOT EXISTS medicamentos_embeddings_embedding_hnsw_idx
ON medicamentos_embeddings
USING hnsw (embedding vector_cosine_ops);
