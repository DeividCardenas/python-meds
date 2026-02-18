CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS medicamentos_embeddings (
    id SERIAL PRIMARY KEY,
    nombre_original TEXT NOT NULL,
    empresa VARCHAR(255) NOT NULL,
    precio NUMERIC(14, 2),
    fu NUMERIC(18, 8),
    vpc NUMERIC(18, 8),
    embedding VECTOR(768) NOT NULL,
    CONSTRAINT medicamentos_embeddings_nombre_empresa_uniq UNIQUE (nombre_original, empresa)
);

CREATE INDEX IF NOT EXISTS medicamentos_embeddings_embedding_hnsw_idx
ON medicamentos_embeddings
USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS medicamentos_embeddings_empresa_idx
ON medicamentos_embeddings (empresa);
