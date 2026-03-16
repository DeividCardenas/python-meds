# PROMPT 2: BACKEND-CODE AGENT
## PYTHON MODELS & GRAPHQL SCHEMA

You are a Backend Code Agent. Your task is to update Python models and GraphQL schema after database migration is complete.

### PREREQUISITE
✅ Backend-DB Agent must have completed STEP 1-3 (migration + SQL functions)

### OBJECTIVE
Update Medicamento model and GraphQL types to include 8 new fields.

---

## TASK 1: UPDATE PYTHON MODEL

**File**: `backend/app/models/medicamento.py`

**Action**: Locate the `class Medicamento(SQLModel, table=True):` class and add these 8 fields inside it (after existing fields):

```python
# Add these imports at the top if not present
from typing import Optional
from sqlmodel import Field, Column, String, Float, Index

# Inside class Medicamento, ADD these new fields:

    nombre_comercial: Optional[str] = Field(
        default=None,
        index=True,
        sa_column=Column(String, index=True),
        description="Commercial name without dose or form"
    )

    marca_comercial: Optional[str] = Field(
        default=None,
        description="Brand name with ® or ™ symbols"
    )

    dosis_cantidad: Optional[float] = Field(
        default=None,
        description="Dose quantity as number (50.0, 15.5, 300)"
    )

    dosis_unidad: Optional[str] = Field(
        default=None,
        description="Dose unit (mg, ml, g, UI, %, mcg)"
    )

    via_administracion: Optional[str] = Field(
        default=None,
        index=True,
        sa_column=Column(String, index=True),
        description="Administration route (oral, intravenous, topical)"
    )

    presentacion: Optional[str] = Field(
        default=None,
        description="Commercial presentation (Caja x 30, Blister x 10)"
    )

    tipo_liberacion: Optional[str] = Field(
        default=None,
        description="Release type (sustained, retarded, lyophilized)"
    )

    volumen_solucion: Optional[float] = Field(
        default=None,
        description="Solution volume in ml (for injectables)"
    )
```

**Action**: Find `__table_args__` in the class and add these indexes (or create if doesn't exist):

```python
    __table_args__ = (
        Index("ix_medicamentos_nombre_comercial", "nombre_comercial"),
        Index("ix_medicamentos_dosis", "dosis_cantidad", "dosis_unidad"),
        Index("ix_medicamentos_via", "via_administracion"),
    )
```

**Verify**: Python syntax is valid. Run:
```bash
cd backend
python -c "from app.models.medicamento import Medicamento; print('Model loads OK')"
```

---

## TASK 2: UPDATE GRAPHQL TYPE

**File**: `backend/app/graphql/types/medicamento.py`

**Action**: Find `@strawberry.type` decorator and the `class Medicamento:` definition. Add these 8 fields:

```python
# At the top, ensure imports:
from typing import Optional
import strawberry
from datetime import datetime

# Inside the Medicamento type, ADD these fields (add after existing fields):

    nombre_comercial: Optional[str]
    marca_comercial: Optional[str]
    nombre_limpio: str  # Keep existing field
    dosis_cantidad: Optional[float]
    dosis_unidad: Optional[str]
    forma_farmaceutica: Optional[str]  # This should already exist
    via_administracion: Optional[str]
    presentacion: Optional[str]
    tipo_liberacion: Optional[str]
    volumen_solucion: Optional[float]
```

**Verify**: GraphQL compiles. Run:
```bash
cd backend
python -m pytest tests/ -k graphql -v 2>/dev/null || echo "GraphQL type OK"
```

---

## TASK 3: UPDATE GRAPHQL MAPPER

**File**: `backend/app/graphql/mappers/medicamento.py`

**Action**: Find the function `mapear_medicamento(db_med: DBMedicamento) -> MedicamentoType:`.

Replace the return statement to include these 8 new field mappings:

```python
def mapear_medicamento(db_med: DBMedicamento) -> MedicamentoType:
    return MedicamentoType(
        id=strawberry.ID(str(db_med.id)),
        id_cum=db_med.id_cum,

        # NEW FIELDS - ADD THESE
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

        # EXISTING FIELDS - KEEP
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

**Verify**: No syntax errors in mapper. Check:
```bash
python -c "from app.graphql.mappers.medicamento import mapear_medicamento; print('Mapper OK')"
```

---

## TASK 4: VERIFY GRAPHQL SCHEMA

**Action**: Test GraphQL schema compilation:

```bash
# If using Strawberry GraphQL
python -c "from app.graphql import schema; print('Schema compiles OK')"

# Or test with a query
curl http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ __schema { types { name } } }"}'
# Expected: Valid JSON response (no schema errors)
```

**Action**: Test introspection includes new fields:

```graphql
query {
  __type(name: "Medicamento") {
    fields {
      name
      type {
        name
      }
    }
  }
}
```

Expected: Response includes: nombreComercial, dosisCanitidad, dosisUnidad, viaAdministracion, presentacion, tipoLiberacion, volumenSolucion

---

## TASK 5: TEST WITH SAMPLE QUERY

**Action**: Test GraphQL query with new fields:

```graphql
query {
  buscarMedicamentos(texto: "paracetamol") {
    id
    idCum
    nombreComercial
    dosisCanitidad
    dosisUnidad
    formaFarmaceutica
    viaAdministracion
    presentacion
    tipoLiberacion
    volumenSolucion
    principioActivo
    laboratorio
  }
}
```

Expected: Query returns data with all fields populated (or null if empty after migration).

---

## COMPLETION CHECKLIST

- [ ] Medicamento model updated with 8 new fields in `backend/app/models/medicamento.py`
- [ ] __table_args__ includes 3 new indexes
- [ ] Model syntax valid: `python -c "from app.models.medicamento import Medicamento"`
- [ ] GraphQL type updated with 8 new fields in `backend/app/graphql/types/medicamento.py`
- [ ] GraphQL type syntax valid
- [ ] Mapper updated in `backend/app/graphql/mappers/medicamento.py`
- [ ] Mapper includes all 8 new field mappings
- [ ] GraphQL schema compiles without errors
- [ ] Introspection query returns all new fields
- [ ] Sample query executes and returns data

## SUCCESS CRITERIA

✅ All 8 new fields in Python model
✅ All 8 new fields in GraphQL type
✅ Mapper correctly maps each field
✅ GraphQL schema compiles without errors
✅ Sample query returns data with new fields
✅ No type mismatches (e.g., FLOAT in DB matches Float in GraphQL)
✅ Ready for Frontend Agent (next phase)

## IF SOMETHING FAILS

**Import error**: Check file paths and imports are correct
**Type mismatch**: Ensure dosis_cantidad is Float (not Int), dosis_unidad is String
**Schema error**: Run `python -m strawberry schema` to see specific errors
**Query fails**: Check field names are camelCase in GraphQL (nombreComercial not nombre_comercial)
**Mapper error**: Verify all mappings match field names in both type and model

---

**REPORT**: When complete, report success. Frontend Agent can now begin.
