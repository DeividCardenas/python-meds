-- Populates / refreshes medicamentos from medicamentos_cum.
-- Safe to run multiple times (UPSERT on id_cum).
INSERT INTO medicamentos (
    id,
    id_cum,
    nombre_limpio,
    laboratorio,
    principio_activo,
    forma_farmaceutica,
    registro_invima,
    atc,
    estado_cum,
    activo,
    embedding_status
)
SELECT
    gen_random_uuid(),
    c.id_cum,
    lower(trim(
        regexp_replace(
            COALESCE(c.descripcioncomercial, c.producto, '')
                || ' '
                || COALESCE(c.principioactivo, ''),
            '\s+', ' ', 'g'
        )
    )) AS nombre_limpio,
    c.titular            AS laboratorio,
    c.principioactivo    AS principio_activo,
    c.formafarmaceutica  AS forma_farmaceutica,
    c.registrosanitario  AS registro_invima,
    c.atc,
    c.estadocum          AS estado_cum,
    lower(COALESCE(c.estadocum, '')) IN ('vigente', 'activo') AS activo,
    'pending'            AS embedding_status
FROM medicamentos_cum c
WHERE c.id_cum IS NOT NULL
ON CONFLICT (id_cum) DO UPDATE SET
    nombre_limpio      = EXCLUDED.nombre_limpio,
    laboratorio        = EXCLUDED.laboratorio,
    principio_activo   = EXCLUDED.principio_activo,
    forma_farmaceutica = EXCLUDED.forma_farmaceutica,
    registro_invima    = EXCLUDED.registro_invima,
    atc                = EXCLUDED.atc,
    estado_cum         = EXCLUDED.estado_cum,
    activo             = EXCLUDED.activo;

SELECT COUNT(*) AS total_medicamentos FROM medicamentos;
