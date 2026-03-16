# PROMPTS CONTEXTUALIZADOS PARA IMPLEMENTACIÓN

---

## 📌 PROMPT 1: BACKEND - MIGRATIONS (Crear Columnas)

**Contexto:** Necesitamos reestructurar la tabla `medicamentos` para mejorar cómo se almacena información farmacéutica. Actualmente, todo está concentrado en una columna `nombre_limpio` que mezcla nombre, dosis y forma de manera poco práctica.

**Problema a resolver:** La columna actual `nombre_limpio = "paracetamol 500mg acetaminofén"` es confusa. Necesitamos separar:
- Nombre comercial (sin dosis ni forma)
- Dosis cantidad y unidad (50, "mg")
- Vía de administración (oral, intravenosa, etc.)
- Presentación (Caja x 30, Blister x 10)
- Tipo de liberación (retardada, normal)

**Tarea:**
Crea una migración Alembic en `backend/alembic/versions/` con el siguiente nombre:
`YYYYMMDD_XXXX_add_medicamento_fields_normalization.py`

**Campos a agregar a tabla `medicamentos`:**
```python
# Campos nuevos
nombre_comercial: VARCHAR (NULL)          # "paracetamol"
marca_comercial: VARCHAR (NULL)           # "IBUPIRAC", "DORMICUM"
dosis_cantidad: FLOAT (NULL)              # 50.0, 15.0, 300.0
dosis_unidad: VARCHAR (NULL)              # "mg", "ml", "%", "g", "UI"
via_administracion: VARCHAR (NULL)        # "oral", "intravenosa", "tópica"
presentacion: VARCHAR (NULL)              # "Caja x 30", "Blister x 10", "Frasco 60 ml"
tipo_forma_detalles: VARCHAR (NULL)       # "recubierta", "dura", "blanda", "liofilizado"
tipo_liberacion: VARCHAR (NULL)           # "retardada", "normal", "liofilizado"
volumen_solucion: FLOAT (NULL)            # Para inyectables: 3.0 (ml)
concentracion_solucion: VARCHAR (NULL)    # "5 mg/ml"

# Campos existentes a optimizar (marcar como NOT NULL si es posible)
# forma_farmaceutica - ya existe, solo normalizar datos
# principio_activo - ya existe
```

**Validaciones:**
- `dosis_cantidad` debe ser FLOAT y > 0 si se proporciona
- `dosis_unidad` debe estar en lista: ['mg', 'ml', 'g', 'UI', '%', 'mcg', 'ug', 'mEq']
- `via_administracion` debe estar en: ['oral', 'intravenosa', 'intramuscular', 'subcutánea', 'tópica', 'vaginal', 'conjuntival', 'intranasal']
- Agregar índices a: `nombre_comercial`, `dosis_unidad`, `via_administracion`

**Índices a crear:**
```sql
CREATE INDEX ix_medicamentos_nombre_comercial ON medicamentos(nombre_comercial);
CREATE INDEX ix_medicamentos_via_adm ON medicamentos(via_administracion);
CREATE INDEX ix_medicamentos_dosis ON medicamentos(dosis_cantidad, dosis_unidad);
```

**Referencia de BD actual:**
```sql
-- La tabla medicamentos actualmente tiene:
-- id (UUID)
-- id_cum (VARCHAR, FK a medicamentos_cum)
-- nombre_limpio (VARCHAR) - ESTO SE MANTIENE PERO SE MEJORA
-- laboratorio (VARCHAR)
-- principio_activo (VARCHAR)
-- forma_farmaceutica (VARCHAR)
-- registro_invima (VARCHAR)
-- atc (VARCHAR)
-- estado_cum (VARCHAR)
-- activo (BOOLEAN)
-- embedding_status (VARCHAR)
```

**Ejemplo de migración estructura:**
```python
def upgrade():
    op.add_column('medicamentos', sa.Column('nombre_comercial', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('dosis_cantidad', sa.Float(), nullable=True))
    # ... más columnas
    op.create_index('ix_medicamentos_nombre_comercial', 'medicamentos', ['nombre_comercial'])

def downgrade():
    op.drop_index('ix_medicamentos_nombre_comercial', table_name='medicamentos')
    op.drop_column('medicamentos', 'nombre_comercial')
    # ... más columns
```

---

## 📌 PROMPT 2: BACKEND - SQL FUNCTIONS (Normalizar Datos)

**Contexto:** Una vez creadas las columnas, necesitamos POBLAR los datos desde `medicamentos_cum` usando transformaciones SQL.

**Datos source:**
- Tabla: `medicamentos_cum` en BD Catalog
- Campos clave: `producto`, `cantidad`, `unidadmedida`, `descripcioncomercial`, `formafarmaceutica`, `viaadministracion`, `unidadreferencia`

**Problema:** Los datos en `medicamentos_cum` están desordenados. Ejemplos:
- `producto = "DICLOFENACO 50 MG TABLETAS"` → nombre="diclofenaco", dosis=50, forma=tableta
- `producto = "SILMAR"` → solo nombre, sin dosis
- `producto = "DORMICUM® AMPOLLAS 15MG/3ML"` → símbolo ®, volumen mixto
- `descripcioncomercial = "CAJA POR 30 TABLETAS"` → presentación = "Caja x 30"

**Tarea:**
Crear archivo SQL en `backend/sql/normalize_medicamentos_campos.sql` con funciones y UPDATE masivos.

**Funciones SQL a crear:**

```sql
-- 1. Extraer nombre comercial limpio
CREATE OR REPLACE FUNCTION extract_nombre_comercial(producto_raw TEXT)
RETURNS TEXT AS $$
BEGIN
  RETURN lower(trim(
    regexp_replace(
      regexp_replace(
        regexp_replace(producto_raw, '[®™©]', '', 'g'),  -- Remover símbolos
        '\d+\s*(mg|ml|ui|%|g|mcg|ug|meq).*', '', 'i'    -- Remover dosis
      ),
      '(tableta|capsula|ampolla|vial|jarabe|locion|gragea|inyectable|solucion|recubierta|blanda|dura).*', '', 'i'
    )
  ));
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- 2. Extraer dosis (cantidad)
CREATE OR REPLACE FUNCTION extract_dosis_cantidad(cantidad_raw TEXT)
RETURNS FLOAT AS $$
BEGIN
  IF cantidad_raw ~ '^\d+\.?\d*$' THEN
    RETURN cantidad_raw::FLOAT;
  END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- 3. Extraer presentación
CREATE OR REPLACE FUNCTION extract_presentacion(descripcion_raw TEXT)
RETURNS TEXT AS $$
BEGIN
  -- Buscar patrones como "CAJA POR 30", "CAJA X 100", "BLISTER X 10"
  IF descripcion_raw ~* 'caja\s+(?:por|x|con)\s+(\d+)' THEN
    RETURN 'Caja x ' || (regexp_matches(descripcion_raw, 'caja\s+(?:por|x|con)\s+(\d+)', 'i'))[1];
  ELSIF descripcion_raw ~* 'blister\s+x\s+(\d+)' THEN
    RETURN 'Blister x ' || (regexp_matches(descripcion_raw, 'blister\s+x\s+(\d+)', 'i'))[1];
  ELSIF descripcion_raw ~* 'frasco\s+(\d+)\s*ml' THEN
    RETURN 'Frasco ' || (regexp_matches(descripcion_raw, 'frasco\s+(\d+)\s*ml', 'i'))[1] || ' ml';
  ELSIF descripcion_raw ~* '(\d+)\s*ml' THEN
    RETURN (regexp_matches(descripcion_raw, '(\d+)\s*ml', 'i'))[1] || ' ml';
  END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- 4. Extraer volumen solución (para inyectables)
CREATE OR REPLACE FUNCTION extract_volumen_solucion(unidad_referencia TEXT)
RETURNS FLOAT AS $$
BEGIN
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

-- 6. Normalizar vía administración
CREATE OR REPLACE FUNCTION normalize_via_administracion(via_raw TEXT, forma_raw TEXT)
RETURNS TEXT AS $$
BEGIN
  -- Si viaadministracion tiene valor válido, usarlo
  IF via_raw NOT IN ('SIN DATO', 'A', 'B', 'C', 'S', '') AND via_raw IS NOT NULL THEN
    RETURN lower(via_raw);
  END IF;

  -- Inferir de forma farmacéutica
  IF forma_raw ~* 'INYECTABLE' THEN
    RETURN 'intravenosa';
  ELSIF forma_raw ~* 'OFTALMICA' THEN
    RETURN 'conjuntival';
  ELSIF forma_raw ~* 'LOCION|CREMA' THEN
    RETURN 'tópica';
  END IF;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- 7. Extraer tipo de liberación
CREATE OR REPLACE FUNCTION extract_tipo_liberacion(producto_raw TEXT)
RETURNS TEXT AS $$
BEGIN
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

-- UPDATE masivo para popular los campos
UPDATE medicamentos m
SET
  nombre_comercial = extract_nombre_comercial(c.producto),
  dosis_cantidad = extract_dosis_cantidad(c.cantidad),
  dosis_unidad = c.unidadmedida,
  via_administracion = normalize_via_administracion(c.viaadministracion, c.formafarmaceutica),
  presentacion = extract_presentacion(c.descripcioncomercial),
  tipo_liberacion = extract_tipo_liberacion(c.producto),
  volumen_solucion = extract_volumen_solucion(c.unidadreferencia),
  forma_farmaceutica = normalize_forma_farmaceutica(c.formafarmaceutica),
  -- Mejorar nombre_limpio existente
  nombre_limpio = lower(trim(
    regexp_replace(
      regexp_replace(
        c.descripcioncomercial || ' ' || c.principioactivo,
        '^\s*caja\s+.*?:\s*', '', 'i'  -- Remover "CAJA CON:"
      ),
      '\s+', ' ', 'g'
    )
  ))
FROM medicamentos_cum c
WHERE m.id_cum = c.id_cum;

-- Validaciones post-update
UPDATE medicamentos
SET dosis_cantidad = NULL
WHERE dosis_cantidad IS NOT NULL AND dosis_cantidad <= 0;

UPDATE medicamentos
SET dosis_unidad = NULL
WHERE dosis_unidad NOT IN ('mg', 'ml', 'g', 'UI', '%', 'mcg', 'ug', 'mEq');
```

**Validar después del update:**
```sql
-- Ver qué se llenó correctamente
SELECT COUNT(*) as total,
       COUNT(nombre_comercial) as con_nombre,
       COUNT(dosis_cantidad) as con_dosis,
       COUNT(via_administracion) as con_via,
       COUNT(presentacion) as con_presentacion
FROM medicamentos;

-- Ver ejemplos
SELECT id_cum, nombre_comercial, dosis_cantidad, dosis_unidad,
       via_administracion, presentacion, tipo_liberacion
FROM medicamentos
LIMIT 10;
```

---

## 📌 PROMPT 3: BACKEND - MODELS (Actualizar SQLModel)

**Contexto:** El modelo `Medicamento` en `backend/app/models/medicamento.py` necesita agregar los nuevos campos.

**Tarea:**
Actualizar la clase `Medicamento` en `backend/app/models/medicamento.py` para incluir los nuevos campos.

**Campos a agregar al modelo:**
```python
# En la clase Medicamento:

# Nuevo campo: nombre comercial (limpio, sin dosis)
nombre_comercial: Optional[str] = Field(
    default=None,
    index=True,
    description="Nombre comercial del medicamento sin dosis ni forma"
)

# Nuevo: marca comercial (si existe)
marca_comercial: Optional[str] = Field(
    default=None,
    description="Marca registrada del medicamento (ej: DORMICUM®, VALCOTE®)"
)

# Nuevo: dosis cantidad
dosis_cantidad: Optional[float] = Field(
    default=None,
    description="Cantidad numérica de dosis (ej: 50, 15.5, 300)"
)

# Nuevo: dosis unidad
dosis_unidad: Optional[str] = Field(
    default=None,
    description="Unidad de medida de dosis (mg, ml, g, UI, %, mcg)"
)

# Nuevo: vía administración
via_administracion: Optional[str] = Field(
    default=None,
    index=True,
    description="Vía de administración (oral, intravenosa, tópica, etc)"
)

# Nuevo: presentación
presentacion: Optional[str] = Field(
    default=None,
    description="Presentación comercial (Caja x 30, Blister x 10, etc)"
)

# Nuevo: tipo de forma (detalles)
tipo_forma_detalles: Optional[str] = Field(
    default=None,
    description="Detalles de la forma (recubierta, dura, blanda, liofilizado)"
)

# Nuevo: tipo de liberación
tipo_liberacion: Optional[str] = Field(
    default=None,
    description="Tipo de liberación (retardada, sostenida, liofilizado)"
)

# Nuevo: volumen solución (inyectables)
volumen_solucion: Optional[float] = Field(
    default=None,
    description="Volumen de solución en ml (para inyectables)"
)

# Nuevo: concentración solución
concentracion_solucion: Optional[str] = Field(
    default=None,
    description="Concentración de solución (ej: 5 mg/ml)"
)
```

**Cambios en índices/constraints:**
```python
# Agregar a __table_args__:
Index("ix_medicamentos_nombre_comercial", "nombre_comercial"),
Index("ix_medicamentos_dosis", "dosis_cantidad", "dosis_unidad"),
Index("ix_medicamentos_via", "via_administracion"),
```

**Campos existentes a verificar:**
- `nombre_limpio` - MANTENER pero ya está mejorado por SQL
- `forma_farmaceutica` - MANTENER, ya tiene constraints
- `principio_activo`, `laboratorio`, `atc` - MANTENER igual

---

## 📌 PROMPT 4: BACKEND - GraphQL Types y Query

**Contexto:** El esquema GraphQL en `backend/app/graphql/` necesita actualizar los tipos para incluir los nuevos campos y que el frontend pueda consultarlos.

**Tarea:**
Actualizar `backend/app/graphql/types/medicamento.py` para agregar los nuevos campos en el tipo `Medicamento`.

**Campos a agregar en GraphQL type:**
```graphql
type Medicamento {
  id: ID!
  idCum: String!

  # Campos mejorados
  nombreComercial: String
  marcaComercial: String
  nombreLimpio: String  # Se mantiene para backward compatibility

  # Dosis
  dosisCanitidad: Float
  dosisUnidad: String

  # Forma y administración
  formaFarmaceutica: String
  tipoFormaDetalles: String
  viaAdministracion: String

  # Presentación
  presentacion: String

  # Liberación y soluciones
  tipoLiberacion: String
  volumenSolucion: Float
  concentracionSolucion: String

  # Existentes
  principioActivo: String
  laboratorio: String
  registroInvima: String
  atc: String
  estadoCum: String
  activo: Boolean

  createdAt: DateTime
  updatedAt: DateTime
}
```

**Actualizar Query:**
```graphql
extend type Query {
  # Query existente mejorado
  buscarMedicamentos(
    texto: String!
    empresa: String
    soloActivos: Boolean = true
    formaFarmaceutica: String
    viaAdministracion: String  # NUEVO FILTRO
    dosisMinima: Float
    dosisMaxima: Float
  ): [Medicamento!]!

  # Query nuevo
  medicamentosPorVia(viaAdministracion: String!): [Medicamento!]!

  medicamentosPorForma(formaFarmaceutica: String!): [Medicamento!]!
}
```

**Mapper a actualizar:**
Actualizar `backend/app/graphql/mappers/medicamento.py` para mapear los nuevos campos desde el modelo al tipo GraphQL.

```python
# En la función que mapea Medicamento:
def mapear_medicamento(db_medicamento) -> MedicamentoType:
    return MedicamentoType(
        id=str(db_medicamento.id),
        idCum=db_medicamento.id_cum,
        nombreComercial=db_medicamento.nombre_comercial,
        marcaComercial=db_medicamento.marca_comercial,
        nombreLimpio=db_medicamento.nombre_limpio,
        dosisCanitidad=db_medicamento.dosis_cantidad,
        dosisUnidad=db_medicamento.dosis_unidad,
        formaFarmaceutica=db_medicamento.forma_farmaceutica,
        viaAdministracion=db_medicamento.via_administracion,
        presentacion=db_medicamento.presentacion,
        tipoLiberacion=db_medicamento.tipo_liberacion,
        # ... resto de campos
    )
```

---

## 📌 PROMPT 5: FRONTEND - Card Component Mejorado

**Contexto:** El componente de tarjeta de medicamentos en `frontend/src/components/BuscadorMedicamentos.tsx` necesita rediseño para mostrar los datos de forma clara y estructurada.

**Tarea:**
Actualizar el componente card (líneas 302-350 en BuscadorMedicamentos.tsx) con nuevo diseño que use los campos normalizados.

**Nuevo componente card:**
```jsx
{/* Card de medicamento mejorada */}
<article
  key={item.id}
  className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition duration-200 hover:scale-105 hover:shadow-lg"
>
  {/* Header: Nombre + Dosis */}
  <div className="flex items-baseline justify-between gap-3 mb-3">
    <div className="flex-1">
      <h3 className="text-lg font-bold text-slate-900">
        {toTitleCase(item.nombreComercial || item.nombreLimpio)}
      </h3>
      {item.dosisCanitidad && (
        <p className="text-sm text-slate-500 mt-1">
          {item.dosisCanitidad} {item.dosisUnidad}
        </p>
      )}
    </p>
    </div>

    {/* Badge regulado */}
    {item.esRegulado && (
      <span className="inline-flex rounded-full bg-orange-100 px-2.5 py-0.5 text-xs font-semibold text-orange-700 whitespace-nowrap">
        🔒 Regulado
      </span>
    )}
  </div>

  {/* Forma + Vía + Liberación como badges */}
  <div className="flex flex-wrap gap-2 mb-3">
    <span className="inline-flex rounded-full bg-blue-100 px-2.5 py-1 text-xs font-medium text-blue-700">
      {toTitleCase(item.formaFarmaceutica)}
    </span>

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

  {/* Principio activo */}
  <p className="text-sm text-slate-600 mb-2">
    <span className="font-medium">{toTitleCase(item.principioActivo)}</span>
  </p>

  {/* Laboratorio */}
  <p className="text-xs text-slate-500 flex items-center gap-2 mb-3">
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-none stroke-current stroke-2">
      <path d="M3 21h18" />
      <path d="M5 21V9l7-4 7 4v12" />
      <path d="M9 21v-4h6v4" />
    </svg>
    {item.laboratorio || "Laboratorio no especificado"}
  </p>

  {/* Presentación si existe */}
  {item.presentacion && (
    <p className="text-xs text-slate-500 mb-3 flex items-center gap-2">
      <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-none stroke-current stroke-2">
        <rect x="3" y="3" width="18" height="18" rx="1" />
      </svg>
      {item.presentacion}
    </p>
  )}

  {/* Precio si existe */}
  {item.precioUnitario && (
    <div className="mb-3 flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
      <span className="text-xs text-slate-500">Precio unitario</span>
      <span className="font-semibold text-slate-900">
        {formatPrice(item.precioUnitario)}
      </span>
    </div>
  )}

  {/* Botón comparativa */}
  <button
    type="button"
    onClick={() => abrirComparativa(item.principioActivo)}
    disabled={!item.principioActivo}
    className="w-full rounded-lg border border-blue-200 px-3 py-2 text-xs font-semibold text-blue-700 transition hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"
  >
    Ver comparativa de precios
  </button>
</article>
```

**Columnas a solicitar del GraphQL:**
Actualizar la query `SearchMedicamentosDocument` para incluir:
```graphql
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
    nombreComercial     # NUEVO
    dosisCanitidad      # NUEVO
    dosisUnidad         # NUEVO
    formaFarmaceutica
    viaAdministracion   # NUEVO
    tipoLiberacion      # NUEVO
    presentacion        # NUEVO
    principioActivo
    laboratorio
    marcaComercial      # NUEVO
    esRegulado
    precioUnitario
    precioMaximoRegulado
    estadoCum
    activo
  }
}
```

---

## 📊 RESUMEN DE IMPLEMENTACIÓN

| Fase | Archivo | Responsable | Duración estimada |
|------|---------|-------------|-------------------|
| 1 | `backend/alembic/versions/YYYYMMDD_XXXX_*.py` | Backend engineer | 1-2 horas |
| 2 | `backend/sql/normalize_medicamentos_campos.sql` | DBA/Backend | 2-3 horas |
| 3 | `backend/app/models/medicamento.py` | Backend engineer | ~30 min |
| 4 | `backend/app/graphql/types/medicamento.py` + mappers | Backend engineer | 1-2 horas |
| 5 | `frontend/src/components/BuscadorMedicamentos.tsx` | Frontend engineer | 2-3 horas |

**Total estimado:** 6-11 horas de trabajo

---

## ✅ CHECKLIST DE VERIFICACIÓN

- [ ] Migrations ejecutadas sin errores
- [ ] SQL functions creadas correctamente
- [ ] UPDATE masivo completó sin problemas
- [ ] Validaciones SQL pasadas
- [ ] Modelos actualizados en Python
- [ ] GraphQL types y queries compiladas
- [ ] Frontend query incluye nuevos campos
- [ ] Card component renderiza correctamente
- [ ] Tests de búsqueda funcionan
- [ ] Tests de GraphQL query ejecutados

---

## 🔗 REFERENCIAS DE DATOS

**Tabla medicamentos_cum en DB:**
```
Campos fuente:
- producto: Nombre + dosis + forma (DESORDENADO)
- descripcioncomercial: Información de presentación + packaging
- cantidad: DOSIS REAL (no concentracion)
- unidadmedida: Unidad de medida (mg, ml, etc)
- formafarmaceutica: Forma farmacéutica
- viaadministracion: Vía de administración
- unidadreferencia: Información contextual (volumen, etc)
- concentracion: CÓDIGOS INÚTILES (A, B, C, S) - IGNORAR
```

**Ejemplos transformados:**
```javascript
// ANTES
{
  producto: "DICLOFENACO 50 MG TABLETAS",
  descripcioncomercial: "CAJA 100 TABLETAS",
  cantidad: "50",
  unidadmedida: "mg",
  formafarmaceutica: "TABLETA CUBIERTA"
}

// DESPUÉS
{
  nombreComercial: "diclofenaco",
  dosisCanitidad: 50,
  dosisUnidad: "mg",
  formaFarmaceutica: "tableta cubierta",
  presentacion: "Caja x 100",
  viaAdministracion: "oral"
}
```
