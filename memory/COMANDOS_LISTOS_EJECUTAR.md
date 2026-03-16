# GUÍA RÁPIDA: COMANDOS Y CÓDIGO PARA IMPLEMENTAR

Esta guía contiene los comandos y código SQL/Python listos para ejecutar o copiar-pegar.

---

## 🚀 PASO 1: Crear y Ejecutar Migration

### Comando para crear migration:
```bash
cd backend
alembic revision --autogenerate -m "Add medicamento normalization fields"
```

### Contenido del archivo generado (`backend/alembic/versions/202603XX_XXXX_add_medicamento_normalization_fields.py`):

```python
"""Add medicamento normalization fields.

Revision ID: add_medicamento_fields
Revises: (obtener de la last revision)
Create Date: 2026-03-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_medicamento_fields'
down_revision = 'ultimo_anterior'  # CAMBIAR CON LA REVISION ANTERIOR
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Agregar columnas nuevas
    op.add_column('medicamentos', sa.Column('nombre_comercial', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('marca_comercial', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('dosis_cantidad', sa.Float(), nullable=True))
    op.add_column('medicamentos', sa.Column('dosis_unidad', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('via_administracion', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('presentacion', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('tipo_forma_detalles', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('tipo_liberacion', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('volumen_solucion', sa.Float(), nullable=True))
    op.add_column('medicamentos', sa.Column('concentracion_solucion', sa.String(), nullable=True))

    # Crear índices
    op.create_index('ix_medicamentos_nombre_comercial', 'medicamentos', ['nombre_comercial'])
    op.create_index('ix_medicamentos_dosis', 'medicamentos', ['dosis_cantidad', 'dosis_unidad'])
    op.create_index('ix_medicamentos_via', 'medicamentos', ['via_administracion'])


def downgrade() -> None:
    # Remover índices
    op.drop_index('ix_medicamentos_via', table_name='medicamentos')
    op.drop_index('ix_medicamentos_dosis', table_name='medicamentos')
    op.drop_index('ix_medicamentos_nombre_comercial', table_name='medicamentos')

    # Remover columnas
    op.drop_column('medicamentos', 'concentracion_solucion')
    op.drop_column('medicamentos', 'volumen_solucion')
    op.drop_column('medicamentos', 'tipo_liberacion')
    op.drop_column('medicamentos', 'tipo_forma_detalles')
    op.drop_column('medicamentos', 'presentacion')
    op.drop_column('medicamentos', 'via_administracion')
    op.drop_column('medicamentos', 'dosis_unidad')
    op.drop_column('medicamentos', 'dosis_cantidad')
    op.drop_column('medicamentos', 'marca_comercial')
    op.drop_column('medicamentos', 'nombre_comercial')
```

### Ejecutar migration:
```bash
alembic upgrade head
```

---

## 🚀 PASO 2: Crear SQL Functions y Hacer UPDATE

### Guardar como archivo: `backend/sql/normalize_medicamentos_campos.sql`

```sql
-- ============================================================
-- FUNCIONES DE NORMALIZACIÓN PARA MEDICAMENTOS
-- ============================================================

-- 1. Extraer nombre comercial limpio (sin dosis, forma, símbolos)
CREATE OR REPLACE FUNCTION extract_nombre_comercial(producto_raw TEXT)
RETURNS TEXT AS $$
BEGIN
  IF producto_raw IS NULL OR trim(producto_raw) = '' THEN
    RETURN NULL;
  END IF;

  RETURN lower(trim(
    regexp_replace(
      regexp_replace(
        regexp_replace(producto_raw, '[®™©]', '', 'g'),
        '\d+\s*(mg|ml|ui|%|g|mcg|ug|meq).*', '', 'i'
      ),
      '(tableta|capsula|ampolla|vial|jarabe|locion|gragea|inyectable|solucion|recubierta|blanda|dura|cubierta).*', '', 'i'
    )
  ));
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- 2. Extraer dosis cantidad (convertir a FLOAT)
CREATE OR REPLACE FUNCTION extract_dosis_cantidad(cantidad_raw TEXT)
RETURNS FLOAT AS $$
BEGIN
  IF cantidad_raw IS NULL OR trim(cantidad_raw) = '' THEN
    RETURN NULL;
  END IF;

  IF cantidad_raw ~ '^\d+\.?\d*$' THEN
    RETURN cantidad_raw::FLOAT;
  END IF;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- 3. Extraer presentación (Caja x #, Blister x #, etc)
CREATE OR REPLACE FUNCTION extract_presentacion(descripcion_raw TEXT)
RETURNS TEXT AS $$
BEGIN
  IF descripcion_raw IS NULL THEN
    RETURN NULL;
  END IF;

  -- CAJA POR/X #
  IF descripcion_raw ~* 'caja\s+(?:por|x|con)\s+(\d+)' THEN
    RETURN 'Caja x ' || (regexp_matches(descripcion_raw, 'caja\s+(?:por|x|con)\s+(\d+)', 'i'))[1];
  END IF;

  -- BLISTER X #
  IF descripcion_raw ~* 'blister\s+x\s+(\d+)' THEN
    RETURN 'Blister x ' || (regexp_matches(descripcion_raw, 'blister\s+x\s+(\d+)', 'i'))[1];
  END IF;

  -- FRASCO # ML
  IF descripcion_raw ~* 'frasco\s+(\d+)\s*ml' THEN
    RETURN 'Frasco ' || (regexp_matches(descripcion_raw, 'frasco\s+(\d+)\s*ml', 'i'))[1] || ' ml';
  END IF;

  -- # ML (genérico)
  IF descripcion_raw ~* '(\d+)\s*ml' THEN
    RETURN (regexp_matches(descripcion_raw, '(\d+)\s*ml', 'i'))[1] || ' ml';
  END IF;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- 4. Extraer volumen solución (para inyectables)
CREATE OR REPLACE FUNCTION extract_volumen_solucion(unidad_referencia TEXT)
RETURNS FLOAT AS $$
BEGIN
  IF unidad_referencia IS NULL THEN
    RETURN NULL;
  END IF;

  IF unidad_referencia ~* '(\d+(?:\.\d+)?)\s*ml' THEN
    RETURN (regexp_matches(unidad_referencia, '(\d+(?:\.\d+)?)\s*ml', 'i'))[1]::FLOAT;
  END IF;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- 5. Normalizar forma farmacéutica
CREATE OR REPLACE FUNCTION normalize_forma_farmaceutica(forma_raw TEXT)
RETURNS TEXT AS $$
BEGIN
  IF forma_raw IS NULL THEN
    RETURN NULL;
  END IF;

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

-- 6. Normalizar vía administración (con fallback)
CREATE OR REPLACE FUNCTION normalize_via_administracion(via_raw TEXT, forma_raw TEXT)
RETURNS TEXT AS $$
BEGIN
  -- Si viaadministracion tiene valor válido, usarlo
  IF via_raw IS NOT NULL AND via_raw NOT IN ('SIN DATO', 'A', 'B', 'C', 'S', '') THEN
    RETURN lower(trim(via_raw));
  END IF;

  -- Inferir de forma farmacéutica
  IF forma_raw IS NOT NULL THEN
    IF forma_raw ~* 'INYECTABLE' THEN
      RETURN 'intravenosa';
    ELSIF forma_raw ~* 'OFTALMICA' THEN
      RETURN 'conjuntival';
    ELSIF forma_raw ~* 'LOCION|CREMA' THEN
      RETURN 'tópica';
    END IF;
  END IF;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- 7. Extraer tipo de liberación
CREATE OR REPLACE FUNCTION extract_tipo_liberacion(producto_raw TEXT)
RETURNS TEXT AS $$
BEGIN
  IF producto_raw IS NULL THEN
    RETURN NULL;
  END IF;

  IF producto_raw ~* 'LIBERACION RETARDADA' THEN
    RETURN 'retardada';
  ELSIF producto_raw ~* 'LIOFILIZADO' THEN
    RETURN 'liofilizado';
  ELSIF producto_raw ~* 'LIBERACION SOSTENIDA' THEN
    RETURN 'sostenida';
  END IF;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================
-- UPDATE MASIVO
-- ============================================================

UPDATE medicamentos m
SET
  nombre_comercial = extract_nombre_comercial(c.producto),
  marca_comercial = CASE
    WHEN c.producto ~* '[®™]' THEN (regexp_matches(c.producto, '^([^\d®™]+)(?:[®™])?', 'i'))[1]
    ELSE NULL
  END,
  dosis_cantidad = extract_dosis_cantidad(c.cantidad),
  dosis_unidad = c.unidadmedida,
  via_administracion = normalize_via_administracion(c.viaadministracion, c.formafarmaceutica),
  presentacion = extract_presentacion(c.descripcioncomercial),
  tipo_liberacion = extract_tipo_liberacion(c.producto),
  volumen_solucion = extract_volumen_solucion(c.unidadreferencia),
  forma_farmaceutica = normalize_forma_farmaceutica(c.formafarmaceutica),
  nombre_limpio = lower(trim(
    regexp_replace(
      COALESCE(c.descripcioncomercial, c.producto, '') || ' ' ||
      COALESCE(c.principioactivo, ''),
      '[\s]+', ' ', 'g'
    )
  ))
FROM medicamentos_cum c
WHERE m.id_cum = c.id_cum;

-- ============================================================
-- VALIDACIONES POST-UPDATE
-- ============================================================

-- Limpiar valores negativos o inválidos
UPDATE medicamentos
SET dosis_cantidad = NULL
WHERE dosis_cantidad IS NOT NULL AND dosis_cantidad <= 0;

-- Validar unidades
UPDATE medicamentos
SET dosis_unidad = NULL
WHERE dosis_unidad NOT IN ('mg', 'ml', 'g', 'UI', '%', 'mcg', 'ug', 'mEq');

-- ============================================================
-- VERIFICACIÓN DE DATOS
-- ============================================================

-- Ver resumen de población
SELECT
  COUNT(*) as total_medicamentos,
  COUNT(nombre_comercial) as con_nombre,
  COUNT(dosis_cantidad) as con_dosis,
  COUNT(via_administracion) as con_via,
  COUNT(presentacion) as con_presentacion,
  COUNT(tipo_liberacion) as con_liberacion
FROM medicamentos;

-- Ver ejemplos
SELECT
  id_cum,
  nombre_comercial,
  dosis_cantidad,
  dosis_unidad,
  forma_farmaceutica,
  via_administracion,
  presentacion,
  tipo_liberacion
FROM medicamentos
LIMIT 10;
```

### Ejecutar SQL:
```bash
# Desde psql o herramienta SQL
psql -U genhospi_admin -h db -d genhospi_catalog -f backend/sql/normalize_medicamentos_campos.sql
```

---

## 🚀 PASO 3: Actualizar Modelo Python

### Archivo: `backend/app/models/medicamento.py`

**Agregar estos campos a la clase Medicamento:**

```python
from typing import Optional
from sqlmodel import Field, Column, String, Float, Index

class Medicamento(SQLModel, table=True):
    __tablename__ = "medicamentos"

    # ... campos existentes ...

    # NUEVOS CAMPOS
    nombre_comercial: Optional[str] = Field(
        default=None,
        index=True,
        sa_column=Column(String, index=True),
        description="Nombre comercial limpio del medicamento"
    )

    marca_comercial: Optional[str] = Field(
        default=None,
        description="Marca registrada (ej: DORMICUM®)"
    )

    dosis_cantidad: Optional[float] = Field(
        default=None,
        description="Cantidad de dosis (50, 15.5, 300)"
    )

    dosis_unidad: Optional[str] = Field(
        default=None,
        description="Unidad (mg, ml, g, UI, %)"
    )

    via_administracion: Optional[str] = Field(
        default=None,
        index=True,
        sa_column=Column(String, index=True),
        description="Vía de administración"
    )

    presentacion: Optional[str] = Field(
        default=None,
        description="Presentación (Caja x 30, Blister x 10)"
    )

    tipo_forma_detalles: Optional[str] = Field(
        default=None,
        description="Detalles (recubierta, dura, blanda)"
    )

    tipo_liberacion: Optional[str] = Field(
        default=None,
        description="Tipo de liberación (retardada, sostenida)"
    )

    volumen_solucion: Optional[float] = Field(
        default=None,
        description="Volumen en ml (inyectables)"
    )

    concentracion_solucion: Optional[str] = Field(
        default=None,
        description="Concentración (ej: 5 mg/ml)"
    )

    # ... resto de campos ...

    __table_args__ = (
        Index("ix_medicamentos_nombre_comercial", "nombre_comercial"),
        Index("ix_medicamentos_dosis", "dosis_cantidad", "dosis_unidad"),
        Index("ix_medicamentos_via", "via_administracion"),
    )
```

---

## 🚀 PASO 4: Actualizar GraphQL

### Archivo: `backend/app/graphql/types/medicamento.py`

```python
from typing import Optional
import strawberry

@strawberry.type
class Medicamento:
    id: strawberry.ID
    id_cum: str

    # NUEVOS CAMPOS
    nombre_comercial: Optional[str]
    marca_comercial: Optional[str]
    nombre_limpio: str  # Mantener para backward compatibility

    # Dosis
    dosis_cantidad: Optional[float]
    dosis_unidad: Optional[str]

    # Forma y administración
    forma_farmaceutica: Optional[str]
    tipo_forma_detalles: Optional[str]
    via_administracion: Optional[str]

    # Presentación
    presentacion: Optional[str]

    # Liberación
    tipo_liberacion: Optional[str]
    volumen_solucion: Optional[float]
    concentracion_solucion: Optional[str]

    # Existentes
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

### Actualizar Mapper: `backend/app/graphql/mappers/medicamento.py`

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
        tipo_forma_detalles=db_med.tipo_forma_detalles,
        via_administracion=db_med.via_administracion,
        presentacion=db_med.presentacion,
        tipo_liberacion=db_med.tipo_liberacion,
        volumen_solucion=db_med.volumen_solucion,
        concentracion_solucion=db_med.concentracion_solucion,
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

### Actualizar Query

```python
@strawberry.type
class Query:
    @strawberry.field
    async def buscar_medicamentos(
        self,
        texto: str,
        empresa: Optional[str] = None,
        solo_activos: bool = True,
        forma_farmaceutica: Optional[str] = None,
        via_administracion: Optional[str] = None,  # NUEVO
    ) -> list[Medicamento]:
        # ... implementación existente ...
        # Agregar filtro: AND via_administracion = ? si se proporciona
```

---

## 🚀 PASO 5: Frontend - Card Component

### Archivo: `frontend/src/components/BuscadorMedicamentos.tsx`

**Reemplazar la sección de card (líneas ~302-350):**

```jsx
{resultados.map((item) => {
  const nombreComercial = toTitleCase(item.nombreComercial || item.nombreLimpio) || "Nombre no disponible";

  return (
    <article
      key={item.id}
      className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition duration-200 hover:scale-105 hover:shadow-lg"
    >
      {/* Header: Nombre + Dosis */}
      <div className="flex items-baseline justify-between gap-3 mb-3">
        <div className="flex-1">
          <h3 className="text-lg font-bold text-slate-900">
            {nombreComercial}
          </h3>
          {item.dosisCanitidad && (
            <p className="text-sm text-slate-500 mt-1">
              {item.dosisCanitidad} {item.dosisUnidad}
            </p>
          )}
        </div>

        {/* Badge Regulado */}
        {item.esRegulado ? (
          <p className="mb-3 inline-flex rounded-full bg-orange-100 px-2.5 py-1 text-xs font-semibold text-orange-700 whitespace-nowrap">
            🔒 Regulado{item.precioMaximoRegulado ? ` · Máx ${formatPrice(item.precioMaximoRegulado)}` : ""}
          </p>
        ) : null}
      </div>

      {/* Badges de características */}
      <div className="flex flex-wrap gap-2 mb-3">
        {item.formaFarmaceutica && (
          <span className="inline-flex rounded-full bg-blue-100 px-2.5 py-1 text-xs font-medium text-blue-700">
            {toTitleCase(item.formaFarmaceutica)}
          </span>
        )}

        {item.viaAdministracion && (
          <span className="inline-flex rounded-full bg-green-100 px-2.5 py-1 text-xs font-medium text-green-700">
            {toTitleCase(item.viaAdministracion)}
          </span>
        )}

        {item.tipoLiberacion && (
          <span className="inline-flex rounded-full bg-purple-100 px-2.5 py-1 text-xs font-medium text-purple-700">
            {toTitleCase(item.tipoLiberacion)}
          </span>
        )}
      </div>

      {/* Estado CUM */}
      {item.estadoCum ? (
        <span
          className={`mb-2 mr-2 inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${
            item.activo
              ? "bg-emerald-100 text-emerald-700"
              : "bg-red-100 text-red-700"
          }`}
        >
          {item.activo ? "✓" : "✗"} {item.estadoCum}
        </span>
      ) : null}

      {/* Principio activo */}
      {item.principioActivo && (
        <p className="text-sm text-slate-600 mb-2">
          <span className="font-medium">{toTitleCase(item.principioActivo)}</span>
        </p>
      )}

      {/* Laboratorio */}
      {item.laboratorio && (
        <p className="mt-2 flex items-center gap-2 text-sm text-slate-600">
          <svg viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current stroke-2" aria-hidden="true">
            <path d="M3 21h18" />
            <path d="M5 21V9l7-4 7 4v12" />
            <path d="M9 21v-4h6v4" />
          </svg>
          {item.laboratorio}
        </p>
      )}

      {/* Presentación */}
      {item.presentacion && (
        <p className="text-xs text-slate-500 mt-2">
          Presentación: <span className="font-medium">{item.presentacion}</span>
        </p>
      )}

      {/* Precio */}
      {item.precioUnitario && (
        <div className="mt-3 flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
          <span className="text-xs text-slate-500">Precio unitario</span>
          <span className="font-semibold text-slate-900">
            {formatPrice(item.precioUnitario)}
          </span>
        </div>
      )}

      {/* Botón Comparativa */}
      <button
        type="button"
        onClick={() => abrirComparativa(item.principioActivo)}
        disabled={!item.principioActivo}
        className="mt-4 w-full rounded-lg border border-blue-200 px-3 py-1.5 text-xs font-semibold text-blue-700 transition hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"
      >
        Ver comparativa de precios
      </button>
    </article>
  );
})}
```

**Actualizar GraphQL Query:**

```typescript
// En BuscadorMedicamentos.tsx, actualizar SearchMedicamentosDocument:

const SearchMedicamentosDocument = gql`
  query SearchMedicamentos(
    $texto: String!
    $empresa: String
    $soloActivos: Boolean
    $formaFarmaceutica: String
  ) {
    buscarMedicamentos(
      texto: $texto
      empresa: $empresa
      soloActivos: $soloActivos
      formaFarmaceutica: $formaFarmaceutica
    ) {
      id
      idCum
      nombreComercial
      marcaComercial
      nombreLimpio
      dosisCanitidad
      dosisUnidad
      formaFarmaceutica
      tipoFormaDetalles
      viaAdministracion
      presentacion
      tipoLiberacion
      volumenSolucion
      concentracionSolucion
      principioActivo
      laboratorio
      registroInvima
      registroInvima
      estadoCum
      activo
      esRegulado
      precioUnitario
      precioMaximoRegulado
    }
  }
`;
```

---

## ✅ CHECKLIST DE EJECUCIÓN

```bash
# 1. Backend - Migration
cd backend
alembic revision --autogenerate -m "Add medicamento normalization fields"
# EDITAR EL ARCHIVO GENERADO CON EL CÓDIGO ARRIBA
alembic upgrade head

# 2. Backend - SQL Functions
# Copiar contenido de normalize_medicamentos_campos.sql a tu BD

# 3. Backend - Models
# Editar backend/app/models/medicamento.py y agregar campos

# 4. Backend - GraphQL
# Editar backend/app/graphql/types/medicamento.py y mapper

# 5. Frontend - Componentes
# Editar frontend/src/components/BuscadorMedicamentos.tsx

# 6. Test
cd frontend
npm run dev
# Verificar que la búsqueda funciona y muestra nuevos campos

# 7. Deploy
# Seguir proceso normal de deployment
```

---

## 🎯 REFERENCIAS RÁPIDAS

**Base de datos - conexión:**
```
Host: db (docker) o localhost (local)
Port: 5432
User: genhospi_admin
Password: MqLGKiZEJ5MJs-N6PifGNXipKWMHP5hL
DB: genhospi_catalog
```

**Estructura medicamentos_cum:**
- `producto` → nombre + dosis (desordenado)
- `cantidad` → DOSIS REAL
- `unidadmedida` → unidad (mg, ml, etc)
- `formafarmaceutica` → forma
- `viaadministracion` → vía (con "SIN DATO")
- `descripcioncomercial` → información de presentación

**Resultados esperados después:**
```sql
SELECT COUNT(*) as con_todas_data
FROM medicamentos
WHERE nombre_comercial IS NOT NULL
  AND dosis_cantidad IS NOT NULL
  AND via_administracion IS NOT NULL;
-- Debería ser cercano al 80-90% del total
```
