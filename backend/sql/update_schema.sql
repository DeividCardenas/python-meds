CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE medicamentos_embeddings
    ADD COLUMN IF NOT EXISTS empresa VARCHAR(255),
    ADD COLUMN IF NOT EXISTS precio NUMERIC(14, 2),
    ADD COLUMN IF NOT EXISTS fu NUMERIC(18, 8),
    ADD COLUMN IF NOT EXISTS vpc NUMERIC(18, 8);

UPDATE medicamentos_embeddings
SET empresa = COALESCE(empresa, 'DESCONOCIDA')
WHERE empresa IS NULL;

ALTER TABLE medicamentos_embeddings
    ALTER COLUMN empresa SET NOT NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'medicamentos_embeddings_nombre_original_key'
          AND conrelid = 'medicamentos_embeddings'::regclass
    ) THEN
        ALTER TABLE medicamentos_embeddings
        DROP CONSTRAINT medicamentos_embeddings_nombre_original_key;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'medicamentos_embeddings_nombre_empresa_uniq'
          AND conrelid = 'medicamentos_embeddings'::regclass
    ) THEN
        ALTER TABLE medicamentos_embeddings
        ADD CONSTRAINT medicamentos_embeddings_nombre_empresa_uniq
        UNIQUE (nombre_original, empresa);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS medicamentos_embeddings_embedding_hnsw_idx
ON medicamentos_embeddings
USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS medicamentos_embeddings_empresa_idx
ON medicamentos_embeddings (empresa);
