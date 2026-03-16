-- Function 1: Extract commercial name (remove dose, form, symbols)
CREATE OR REPLACE FUNCTION extract_nombre_comercial(producto_raw TEXT)
RETURNS TEXT AS $$
DECLARE
  v_clean TEXT;
BEGIN
  IF producto_raw IS NULL OR trim(producto_raw) = '' THEN RETURN NULL; END IF;
  v_clean := lower(trim(producto_raw));
  v_clean := regexp_replace(v_clean, '[®™©]', '', 'g');
  v_clean := regexp_replace(v_clean, '\d+(?:[\.,]\d+)?\s?(mg|ml|ui|%|g|mcg|ug|meq)', ' ', 'gi');
  v_clean := regexp_replace(v_clean, '(tableta|capsula|c[\?aá]psula|ampolla|vial|jarabe|locion|loci[oó]n|gragea|inyectable|soluci[oó]\??n|recubierta|blanda|dura|cubierta)', ' ', 'gi');
  v_clean := regexp_replace(v_clean, '[^[:alpha:]\s]', ' ', 'g');
  v_clean := regexp_replace(v_clean, '\s+', ' ', 'g');
  v_clean := trim(v_clean);
  IF v_clean = '' THEN RETURN NULL; END IF;
  RETURN v_clean;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function 2: Extract dose quantity (as FLOAT)
CREATE OR REPLACE FUNCTION extract_dosis_cantidad(cantidad_raw TEXT)
RETURNS FLOAT AS $$
BEGIN
  IF cantidad_raw IS NULL OR trim(cantidad_raw) = '' THEN RETURN NULL; END IF;
  IF cantidad_raw ~ '^\d+\.?\d*$' THEN RETURN cantidad_raw::FLOAT; END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function 3: Extract presentation (Caja x 30, Blister x 10, etc)
CREATE OR REPLACE FUNCTION extract_presentacion(descripcion_raw TEXT)
RETURNS TEXT AS $$
DECLARE
  v_match TEXT;
BEGIN
  IF descripcion_raw IS NULL THEN RETURN NULL; END IF;

  v_match := substring(descripcion_raw FROM '(?i)caja[^\d]*(?:por|x|con)\s*(\d+)');
  IF v_match IS NOT NULL THEN RETURN 'Caja x ' || v_match; END IF;

  v_match := substring(descripcion_raw FROM '(?i)blister[^\d]*(?:por|x|con)?\s*(\d+)');
  IF v_match IS NOT NULL THEN RETURN 'Blister x ' || v_match; END IF;

  v_match := substring(descripcion_raw FROM '(?i)(\d+)\s*(tabletas|c[áa\?]psulas|capsulas|comprimidos|grageas|ampollas|viales|sobres)');
  IF v_match IS NOT NULL THEN RETURN 'Caja x ' || v_match; END IF;

  v_match := substring(descripcion_raw FROM '(?i)frasco[^\d]*(\d+(?:[\.,]\d+)?)\s*ml');
  IF v_match IS NOT NULL THEN RETURN 'Frasco ' || replace(v_match, ',', '.') || ' ml'; END IF;

  v_match := substring(descripcion_raw FROM '(?i)(\d+(?:[\.,]\d+)?)\s*ml');
  IF v_match IS NOT NULL THEN RETURN replace(v_match, ',', '.') || ' ml'; END IF;

  v_match := substring(descripcion_raw FROM '(?i)x\s*(\d+)');
  IF v_match IS NOT NULL THEN RETURN 'Caja x ' || v_match; END IF;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function 4: Extract solution volume (for injectables)
CREATE OR REPLACE FUNCTION extract_volumen_solucion(unidad_referencia TEXT)
RETURNS FLOAT AS $$
BEGIN
  IF unidad_referencia IS NULL THEN RETURN NULL; END IF;
  IF unidad_referencia ~* '(\d+(?:\.\d+)?)\s*ml' THEN RETURN (regexp_matches(unidad_referencia, '(\d+(?:\.\d+)?)\s*ml', 'i'))[1]::FLOAT; END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function 5: Normalize pharmaceutical form
CREATE OR REPLACE FUNCTION normalize_forma_farmaceutica(forma_raw TEXT)
RETURNS TEXT AS $$
DECLARE
  v_forma TEXT;
  v_clean TEXT;
BEGIN
  IF forma_raw IS NULL THEN RETURN NULL; END IF;
  v_forma := lower(trim(forma_raw));
  IF v_forma ~* 'tableta cubierta con pelicula' THEN RETURN 'tableta cubierta'; END IF;
  IF v_forma ~* 'tableta recubierta' THEN RETURN 'tableta recubierta'; END IF;
  IF v_forma ~* 'tableta cubierta \(gragea\)' THEN RETURN 'gragea'; END IF;
  IF v_forma ~* '^tableta$' THEN RETURN 'tableta'; END IF;
  IF v_forma ~* 'c.?psula dura|capsula dura' THEN RETURN 'cápsula dura'; END IF;
  IF v_forma ~* 'c.?psula blanda|capsula blanda' THEN RETURN 'cápsula blanda'; END IF;
  IF v_forma ~* 'soluci.?n inyectable' THEN RETURN 'solución inyectable'; END IF;
  IF v_forma ~* 'soluci.?n oftalmica|soluci.?n oft[áa]lmica' THEN RETURN 'solución oftálmica'; END IF;
  IF v_forma ~* 'soluci.?n oral' THEN RETURN 'solución oral'; END IF;
  IF v_forma ~* 'loci.?n|locion' THEN RETURN 'loción'; END IF;
  IF v_forma ~* '^gragea$' THEN RETURN 'gragea'; END IF;
  v_clean := lower(trim(regexp_replace(forma_raw, '[^[:alpha:]\s]', ' ', 'g')));
  v_clean := regexp_replace(v_clean, '\s+', ' ', 'g');
  RETURN trim(v_clean);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function 6: Normalize administration route (with fallback inference)
CREATE OR REPLACE FUNCTION normalize_via_administracion(via_raw TEXT, forma_raw TEXT)
RETURNS TEXT AS $$
BEGIN
  IF via_raw IS NOT NULL AND via_raw NOT IN ('SIN DATO', 'A', 'B', 'C', 'S', '') THEN RETURN lower(trim(via_raw)); END IF;
  IF forma_raw IS NOT NULL THEN
    IF forma_raw ~* 'INYECTABLE' THEN RETURN 'intravenosa'; END IF;
    IF forma_raw ~* 'OFTALMICA' THEN RETURN 'conjuntival'; END IF;
    IF forma_raw ~* 'LOCION|CREMA' THEN RETURN 'tópica'; END IF;
  END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function 7: Extract release type
CREATE OR REPLACE FUNCTION extract_tipo_liberacion(producto_raw TEXT)
RETURNS TEXT AS $$
BEGIN
  IF producto_raw IS NULL THEN RETURN NULL; END IF;
  IF producto_raw ~* 'LIBERACION RETARDADA' THEN RETURN 'retardada'; END IF;
  IF producto_raw ~* 'LIOFILIZADO' THEN RETURN 'liofilizado'; END IF;
  IF producto_raw ~* 'LIBERACION SOSTENIDA' THEN RETURN 'sostenida'; END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- BULK UPDATE: Populate all new fields
BEGIN;

UPDATE medicamentos m
SET
  nombre_comercial = extract_nombre_comercial(c.producto),
  marca_comercial = (
    SELECT trim(substring(c2.producto FROM '^([^0-9]*?[®™])'))
    FROM medicamentos_cum c2
    WHERE c2.id_cum = m.id_cum
      AND c2.producto ~* '[®™]'
    ORDER BY c2.producto
    LIMIT 1
  ),
  dosis_cantidad = extract_dosis_cantidad(c.cantidad),
  dosis_unidad = c.unidadmedida,
  via_administracion = normalize_via_administracion(c.viaadministracion, c.formafarmaceutica),
  presentacion = COALESCE(
    extract_presentacion(c.descripcioncomercial),
    extract_presentacion(c.unidadreferencia),
    extract_presentacion(c.producto)
  ),
  tipo_liberacion = extract_tipo_liberacion(c.producto),
  volumen_solucion = extract_volumen_solucion(c.unidadreferencia),
  forma_farmaceutica = normalize_forma_farmaceutica(c.formafarmaceutica),
  nombre_limpio = COALESCE(extract_nombre_comercial(c.producto), extract_nombre_comercial(c.principioactivo), '')
FROM medicamentos_cum c
WHERE m.id_cum = c.id_cum;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS ix_medicamentos_nombre_comercial_trgm
ON medicamentos USING gin (nombre_comercial gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_medicamentos_laboratorio_trgm
ON medicamentos USING gin (laboratorio gin_trgm_ops);

COMMIT;

-- VALIDATION QUERIES
SELECT COUNT(*) as total,
       COUNT(nombre_comercial) as con_nombre,
       COUNT(dosis_cantidad) as con_dosis,
       COUNT(via_administracion) as con_via,
       COUNT(presentacion) as con_presentacion
FROM medicamentos;

-- Sample rows to verify transformations
SELECT id_cum, nombre_comercial, dosis_cantidad, dosis_unidad,
       forma_farmaceutica, via_administracion, presentacion
FROM medicamentos
LIMIT 10;
