# PROMPT 1: BACKEND-DB AGENT
## DATABASE MIGRATION & SQL FUNCTIONS

You are a Backend Database Agent. Your task is to implement database normalization for medicamentos table.

### OBJECTIVE
Create Alembic migration and SQL normalization functions to normalize medicamento data.

### CURRENT STATE
- Table `medicamentos` has field `nombre_limpio` containing mixed data: name + dose + form
- Field `cantidad` contains actual dose (NOT in `concentracion`)
- Data needs to be normalized into 8 separate columns

### TASK BREAKDOWN

## STEP 1: CREATE ALEMBIC MIGRATION

**File**: `backend/alembic/versions/[YYYYMMDD]_[XXXX]_add_medicamento_normalization_fields.py`

**Action**: Create new migration file with this exact content:

```python
"""Add medicamento normalization fields.

Revision ID: add_medicamento_fields
Revises: [PREVIOUS_REVISION_ID]
Create Date: 2026-03-16

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_medicamento_fields'
down_revision = '[FIND_PREVIOUS_REVISION_ID]'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('medicamentos', sa.Column('nombre_comercial', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('marca_comercial', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('dosis_cantidad', sa.Float(), nullable=True))
    op.add_column('medicamentos', sa.Column('dosis_unidad', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('via_administracion', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('presentacion', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('tipo_liberacion', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('volumen_solucion', sa.Float(), nullable=True))

    op.create_index('ix_medicamentos_nombre_comercial', 'medicamentos', ['nombre_comercial'])
    op.create_index('ix_medicamentos_dosis', 'medicamentos', ['dosis_cantidad', 'dosis_unidad'])
    op.create_index('ix_medicamentos_via', 'medicamentos', ['via_administracion'])


def downgrade() -> None:
    op.drop_index('ix_medicamentos_via', table_name='medicamentos')
    op.drop_index('ix_medicamentos_dosis', table_name='medicamentos')
    op.drop_index('ix_medicamentos_nombre_comercial', table_name='medicamentos')

    op.drop_column('medicamentos', 'volumen_solucion')
    op.drop_column('medicamentos', 'tipo_liberacion')
    op.drop_column('medicamentos', 'presentacion')
    op.drop_column('medicamentos', 'via_administracion')
    op.drop_column('medicamentos', 'dosis_unidad')
    op.drop_column('medicamentos', 'dosis_cantidad')
    op.drop_column('medicamentos', 'marca_comercial')
    op.drop_column('medicamentos', 'nombre_comercial')
```

**Execute**:
```bash
cd backend
alembic upgrade head
```

**Verify**: All 8 columns created, 3 indexes created. Check logs for "OK" or success message.

---

## STEP 2: CREATE SQL FUNCTIONS

**File**: `backend/sql/normalize_medicamentos_campos.sql`

**Action**: Create file with 7 normalization functions:

```sql
-- Function 1: Extract commercial name (remove dose, form, symbols)
CREATE OR REPLACE FUNCTION extract_nombre_comercial(producto_raw TEXT)
RETURNS TEXT AS $$
BEGIN
  IF producto_raw IS NULL OR trim(producto_raw) = '' THEN RETURN NULL; END IF;
  RETURN lower(trim(regexp_replace(regexp_replace(regexp_replace(producto_raw, '[®™©]', '', 'g'), '\d+\s?(mg|ml|ui|%|g|mcg|ug|meq).*', '', 'i'), '(tableta|capsula|ampolla|vial|jarabe|locion|gragea|inyectable|solucion|recubierta|blanda|dura|cubierta).*', '', 'i')));
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
BEGIN
  IF descripcion_raw IS NULL THEN RETURN NULL; END IF;
  IF descripcion_raw ~* 'caja\s+(?:por|x|con)\s+(\d+)' THEN RETURN 'Caja x ' || (regexp_matches(descripcion_raw, 'caja\s+(?:por|x|con)\s+(\d+)', 'i'))[1]; END IF;
  IF descripcion_raw ~* 'blister\s+x\s+(\d+)' THEN RETURN 'Blister x ' || (regexp_matches(descripcion_raw, 'blister\s+x\s+(\d+)', 'i'))[1]; END IF;
  IF descripcion_raw ~* 'frasco\s+(\d+)\s*ml' THEN RETURN 'Frasco ' || (regexp_matches(descripcion_raw, 'frasco\s+(\d+)\s*ml', 'i'))[1] || ' ml'; END IF;
  IF descripcion_raw ~* '(\d+)\s*ml' THEN RETURN (regexp_matches(descripcion_raw, '(\d+)\s*ml', 'i'))[1] || ' ml'; END IF;
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
BEGIN
  IF forma_raw IS NULL THEN RETURN NULL; END IF;
  RETURN CASE lower(trim(forma_raw))
    WHEN 'tableta' THEN 'tableta'
    WHEN 'tableta cubierta' THEN 'tableta cubierta'
    WHEN 'tableta cubierta con pelicula' THEN 'tableta cubierta'
    WHEN 'tableta recubierta' THEN 'tableta recubierta'
    WHEN 'tableta cubierta (gragea)' THEN 'gragea'
    WHEN 'capsula dura' THEN 'cápsula dura'
    WHEN 'capsula blanda' THEN 'cápsula blanda'
    WHEN 'solucion inyectable' THEN 'solución inyectable'
    WHEN 'solucion oftalmica' THEN 'solución oftálmica'
    WHEN 'locion' THEN 'loción'
    WHEN 'gragea' THEN 'gragea'
    ELSE lower(forma_raw)
  END;
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
  marca_comercial = CASE WHEN c.producto ~* '[®™]' THEN (regexp_matches(c.producto, '^([^\d®™]+)(?:[®™])?', 'i'))[1] ELSE NULL END,
  dosis_cantidad = extract_dosis_cantidad(c.cantidad),
  dosis_unidad = c.unidadmedida,
  via_administracion = normalize_via_administracion(c.viaadministracion, c.formafarmaceutica),
  presentacion = extract_presentacion(c.descripcioncomercial),
  tipo_liberacion = extract_tipo_liberacion(c.producto),
  volumen_solucion = extract_volumen_solucion(c.unidadreferencia),
  forma_farmaceutica = normalize_forma_farmaceutica(c.formafarmaceutica),
  nombre_limpio = lower(trim(regexp_replace(COALESCE(c.descripcioncomercial, c.producto, '') || ' ' || COALESCE(c.principioactivo, ''), '[\s]+', ' ', 'g')))
FROM medicamentos_cum c
WHERE m.id_cum = c.id_cum;

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
```

**Execute**: Run this SQL file in your database. Expected: All 7 functions created, UPDATE completes successfully, validation queries show 80%+ population.

---

## STEP 3: VERIFY RESULTS

**Run these validation checks**:

```sql
-- Check: Do we have enough data?
SELECT COUNT(*) total,
       COUNT(nombre_comercial) with_name,
       COUNT(dosis_cantidad) with_dose,
       COUNT(dosis_unidad) with_unit,
       COUNT(via_administracion) with_via
FROM medicamentos;
-- Expected: 80%+ populated for each

-- Check: Sample data looks correct
SELECT id_cum, nombre_comercial, dosis_cantidad, dosis_unidad
FROM medicamentos
WHERE nombre_comercial IS NOT NULL
LIMIT 5;
-- Expected: nombre_comercial without numbers/symbols, dosis_cantidad as numbers

-- Check: Indexes created
SELECT * FROM pg_indexes
WHERE tablename = 'medicamentos'
AND indexname LIKE 'ix_medicamentos%';
-- Expected: 3 indexes visible
```

---

## COMPLETION CHECKLIST

- [ ] Migration file created: `backend/alembic/versions/[DATE]_[XXXX]_add_medicamento_normalization_fields.py`
- [ ] Migration executed: `alembic upgrade head`
- [ ] SQL functions file created: `backend/sql/normalize_medicamentos_campos.sql`
- [ ] All 7 functions created in database
- [ ] UPDATE query executed successfully
- [ ] Validation queries show 80%+ population
- [ ] 8 new columns visible in medicamentos table
- [ ] 3 indexes created

## SUCCESS CRITERIA

✅ All 8 columns present in medicamentos table
✅ All 7 SQL functions created without errors
✅ UPDATE query completed without errors
✅ 80%+ of medicamentos have data in new columns
✅ Validation queries return expected results
✅ Ready for Backend-Code Agent (next phase)

## IF SOMETHING FAILS

**Migration failed**: Run `alembic downgrade -1`, check migration syntax, retry
**SQL functions fail**: Check syntax in the SQL file, try creating one function at a time
**UPDATE hung/slow**: This is normal for first run, wait up to 60 seconds
**Validation shows < 80%**: Check medicamentos_cum table has data, review transformation logic

---

**REPORT**: When complete, report success and pass control to Backend-Code Agent
