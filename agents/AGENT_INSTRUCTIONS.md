# AGENT INSTRUCTIONS: MEDICAMENTOS NORMALIZATION

## OBJECTIVE
Normalize medicamento data structure. Separate mixed fields into atomic units.

## PROBLEM
- Field `nombre_limpio` contains: `nombre + dosis + forma`
- Field `cantidad` contains actual dose (NOT in `concentracion`)
- Field `descripcioncomercial` contains presentation info (not structured)
- No separate columns for: dosis, via_administracion, presentacion, tipo_liberacion

## SOLUTION
Create 8 new columns in `medicamentos` table and populate with normalized data from `medicamentos_cum`.

---

## PHASE 1: DATABASE MIGRATION

### TASK: Create Alembic Migration

**File**: `backend/alembic/versions/[YYYYMMDD]_[XXXX]_add_medicamento_normalization_fields.py`

**Action**:
```python
def upgrade():
    # Add 8 columns
    op.add_column('medicamentos', sa.Column('nombre_comercial', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('marca_comercial', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('dosis_cantidad', sa.Float(), nullable=True))
    op.add_column('medicamentos', sa.Column('dosis_unidad', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('via_administracion', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('presentacion', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('tipo_liberacion', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('volumen_solucion', sa.Float(), nullable=True))

    # Create indexes
    op.create_index('ix_medicamentos_nombre_comercial', 'medicamentos', ['nombre_comercial'])
    op.create_index('ix_medicamentos_dosis', 'medicamentos', ['dosis_cantidad', 'dosis_unidad'])
    op.create_index('ix_medicamentos_via', 'medicamentos', ['via_administracion'])

def downgrade():
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

---

## PHASE 2: SQL NORMALIZATION FUNCTIONS

### TASK: Create Functions & Execute Update

**File**: `backend/sql/normalize_medicamentos_campos.sql`

**Functions**:

```sql
-- Function 1: Extract comercial name (remove dose, form, symbols)
CREATE OR REPLACE FUNCTION extract_nombre_comercial(producto_raw TEXT)
RETURNS TEXT AS $$
BEGIN
  IF producto_raw IS NULL OR trim(producto_raw) = '' THEN RETURN NULL; END IF;
  RETURN lower(trim(regexp_replace(regexp_replace(regexp_replace(producto_raw, '[®™©]', '', 'g'), '\d+\s?(mg|ml|ui|%|g|mcg|ug|meq).*', '', 'i'), '(tableta|capsula|ampolla|vial|jarabe|locion|gragea|inyectable|solucion|recubierta|blanda|dura|cubierta).*', '', 'i')));
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function 2: Extract dose quantity (float)
CREATE OR REPLACE FUNCTION extract_dosis_cantidad(cantidad_raw TEXT)
RETURNS FLOAT AS $$
BEGIN
  IF cantidad_raw IS NULL OR trim(cantidad_raw) = '' THEN RETURN NULL; END IF;
  IF cantidad_raw ~ '^\d+\.?\d*$' THEN RETURN cantidad_raw::FLOAT; END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function 3: Extract presentation (parse descripcioncomercial)
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

-- Function 4: Extract solution volume (injectables)
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

-- Function 6: Normalize administration route (with fallback)
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
```

**Execute Update**:
```sql
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
```

**Validation**:
```sql
-- Check results
SELECT COUNT(*) as total, COUNT(nombre_comercial) as con_nombre, COUNT(dosis_cantidad) as con_dosis, COUNT(via_administracion) as con_via FROM medicamentos;

-- Sample rows
SELECT id_cum, nombre_comercial, dosis_cantidad, dosis_unidad, forma_farmaceutica, via_administracion, presentacion FROM medicamentos LIMIT 10;
```

---

## PHASE 3: PYTHON MODEL UPDATE

### TASK: Update Medicamento Model

**File**: `backend/app/models/medicamento.py`

**Changes**:

```python
from typing import Optional
from sqlmodel import Field, Column, String, Float, Index

class Medicamento(SQLModel, table=True):
    __tablename__ = "medicamentos"

    # NEW FIELDS
    nombre_comercial: Optional[str] = Field(default=None, index=True, sa_column=Column(String, index=True))
    marca_comercial: Optional[str] = Field(default=None)
    dosis_cantidad: Optional[float] = Field(default=None)
    dosis_unidad: Optional[str] = Field(default=None)
    via_administracion: Optional[str] = Field(default=None, index=True, sa_column=Column(String, index=True))
    presentacion: Optional[str] = Field(default=None)
    tipo_liberacion: Optional[str] = Field(default=None)
    volumen_solucion: Optional[float] = Field(default=None)

    __table_args__ = (
        Index("ix_medicamentos_nombre_comercial", "nombre_comercial"),
        Index("ix_medicamentos_dosis", "dosis_cantidad", "dosis_unidad"),
        Index("ix_medicamentos_via", "via_administracion"),
    )
```

---

## PHASE 4: GRAPHQL SCHEMA UPDATE

### TASK: Update GraphQL Types & Mappers

**File**: `backend/app/graphql/types/medicamento.py`

```python
import strawberry
from typing import Optional
from datetime import datetime

@strawberry.type
class Medicamento:
    id: strawberry.ID
    id_cum: str
    nombre_comercial: Optional[str]
    marca_comercial: Optional[str]
    nombre_limpio: str
    dosis_cantidad: Optional[float]
    dosis_unidad: Optional[str]
    forma_farmaceutica: Optional[str]
    via_administracion: Optional[str]
    presentacion: Optional[str]
    tipo_liberacion: Optional[str]
    volumen_solucion: Optional[float]
    principio_activo: Optional[str]
    laboratorio: Optional[str]
    registro_invima: Optional[str]
    atc: Optional[str]
    estado_cum: Optional[str]
    activo: bool
    es_regulado: bool
    precio_unitario: Optional[float]
    precio_maximo_regulado: Optional[float]
    created_at: datetime
    updated_at: datetime
```

**File**: `backend/app/graphql/mappers/medicamento.py`

```python
from app.models.medicamento import Medicamento as DBMedicamento
from app.graphql.types.medicamento import Medicamento as MedicamentoType

def mapear_medicamento(db_med: DBMedicamento) -> MedicamentoType:
    return MedicamentoType(
        id=strawberry.ID(str(db_med.id)),
        id_cum=db_med.id_cum,
        nombre_comercial=db_med.nombre_comercial,
        marca_comercial=db_med.marca_comercial,
        nombre_limpio=db_med.nombre_limpio,
        dosis_cantidad=db_med.dosis_cantidad,
        dosis_unidad=db_med.dosis_unidad,
        forma_farmaceutica=db_med.forma_farmaceutica,
        via_administracion=db_med.via_administracion,
        presentacion=db_med.presentacion,
        tipo_liberacion=db_med.tipo_liberacion,
        volumen_solucion=db_med.volumen_solucion,
        principio_activo=db_med.principio_activo,
        laboratorio=db_med.laboratorio,
        registro_invima=db_med.registro_invima,
        atc=db_med.atc,
        estado_cum=db_med.estado_cum,
        activo=db_med.activo,
        es_regulado=db_med.es_regulado,
        precio_unitario=db_med.precio_unitario,
        precio_maximo_regulado=db_med.precio_maximo_regulado,
        created_at=db_med.created_at,
        updated_at=db_med.updated_at,
    )
```

---

## PHASE 5: FRONTEND COMPONENT UPDATE

### TASK: Update BuscadorMedicamentos Card Component

**File**: `frontend/src/components/BuscadorMedicamentos.tsx`

**Replace lines 302-350** with:

```jsx
<article key={item.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:scale-105 hover:shadow-lg">
  <div className="flex items-baseline justify-between gap-3 mb-3">
    <div className="flex-1">
      <h3 className="text-lg font-bold text-slate-900">{toTitleCase(item.nombreComercial || item.nombreLimpio)}</h3>
      {item.dosisCanitidad && <p className="text-sm text-slate-500 mt-1">{item.dosisCanitidad} {item.dosisUnidad}</p>}
    </div>
    {item.esRegulado && <span className="inline-flex rounded-full bg-orange-100 px-2.5 py-0.5 text-xs font-semibold text-orange-700 whitespace-nowrap">🔒 Regulado{item.precioMaximoRegulado ? ` · Máx ${formatPrice(item.precioMaximoRegulado)}` : ""}</span>}
  </div>

  <div className="flex flex-wrap gap-2 mb-3">
    {item.formaFarmaceutica && <span className="inline-flex rounded-full bg-blue-100 px-2.5 py-1 text-xs font-medium text-blue-700">{toTitleCase(item.formaFarmaceutica)}</span>}
    {item.viaAdministracion && <span className="inline-flex rounded-full bg-green-100 px-2.5 py-1 text-xs font-medium text-green-700">{toTitleCase(item.viaAdministracion)}</span>}
    {item.tipoLiberacion && <span className="inline-flex rounded-full bg-purple-100 px-2.5 py-1 text-xs font-medium text-purple-700">{toTitleCase(item.tipoLiberacion)}</span>}
  </div>

  {item.estadoCum && <span className={`mb-2 mr-2 inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${item.activo ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>{item.activo ? "✓" : "✗"} {item.estadoCum}</span>}

  {item.principioActivo && <p className="text-sm text-slate-600 mb-2"><span className="font-medium">{toTitleCase(item.principioActivo)}</span></p>}

  {item.laboratorio && <p className="mt-2 flex items-center gap-2 text-sm text-slate-600"><svg viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current stroke-2"><path d="M3 21h18" /><path d="M5 21V9l7-4 7 4v12" /><path d="M9 21v-4h6v4" /></svg>{item.laboratorio}</p>}

  {item.presentacion && <p className="text-xs text-slate-500 mt-2">Presentación: <span className="font-medium">{item.presentacion}</span></p>}

  {item.precioUnitario && <div className="mt-3 flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2"><span className="text-xs text-slate-500">Precio unitario</span><span className="font-semibold text-slate-900">{formatPrice(item.precioUnitario)}</span></div>}

  <button type="button" onClick={() => abrirComparativa(item.principioActivo)} disabled={!item.principioActivo} className="mt-4 w-full rounded-lg border border-blue-200 px-3 py-1.5 text-xs font-semibold text-blue-700 transition hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50">Ver comparativa de precios</button>
</article>
```

**Update GraphQL Query**:

```graphql
query SearchMedicamentos($texto: String!, $empresa: String, $soloActivos: Boolean, $formaFarmaceutica: String) {
  buscarMedicamentos(texto: $texto, empresa: $empresa, soloActivos: $soloActivos, formaFarmaceutica: $formaFarmaceutica) {
    id
    idCum
    nombreComercial
    marcaComercial
    nombreLimpio
    dosisCanitidad
    dosisUnidad
    formaFarmaceutica
    viaAdministracion
    presentacion
    tipoLiberacion
    volumenSolucion
    principioActivo
    laboratorio
    registroInvima
    estadoCum
    activo
    esRegulado
    precioUnitario
    precioMaximoRegulado
  }
}
```

---

## VALIDATION CHECKLIST

- [ ] Migration executed: `alembic upgrade head`
- [ ] SQL functions created in DB
- [ ] UPDATE query completed (80-90% medicamentos populated)
- [ ] Python model updated with 8 new fields
- [ ] GraphQL types updated
- [ ] GraphQL mappers updated
- [ ] Frontend card component updated
- [ ] Frontend query updated
- [ ] Local testing: `npm run dev`
- [ ] No console errors
- [ ] Card renders with new fields
- [ ] Search functionality works

---

## DATA VALIDATION QUERIES

```sql
-- Check population levels
SELECT COUNT(*) total,
       COUNT(nombre_comercial) with_name,
       COUNT(dosis_cantidad) with_dose,
       COUNT(via_administracion) with_via
FROM medicamentos;

-- Check for nulls
SELECT id_cum, nombre_comercial, dosis_cantidad, dosis_unidad, via_administracion
FROM medicamentos
WHERE nombre_comercial IS NULL
LIMIT 5;

-- Sample of populated data
SELECT id_cum, nombre_comercial, dosis_cantidad, dosis_unidad, forma_farmaceutica, via_administracion, presentacion
FROM medicamentos
LIMIT 10;
```

---

## ROLLBACK PROCEDURE

```bash
cd backend
alembic downgrade -1
```

This reverts the migration and removes all 8 columns.

---

## COMPLETION CRITERIA

1. ✅ 8 new columns created in medicamentos table
2. ✅ 7 SQL functions executed successfully
3. ✅ UPDATE query populated 80%+ of medicamentos
4. ✅ Python models updated with new fields
5. ✅ GraphQL schema includes new fields
6. ✅ Frontend card displays new data correctly
7. ✅ Search/filter functionality works
8. ✅ No database errors
9. ✅ No GraphQL errors
10. ✅ No frontend console errors
