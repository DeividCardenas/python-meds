# Análisis Detallado: Columna "PRODUCTO" en medicamentos_cum

## 📊 EJEMPLOS REALES DEL CSV

| Producto | Problemas | Debería ser |
|----------|-----------|------------|
| `FLUNARICINA 10 MG` | ⚠️ Sin forma farmacéutica | "flunaricina" (dosis: "10 mg") |
| `IBUPROFENO 500 MG TABLETAS` | ✅ Consistente | nombre: "ibuprofeno", dosis: "500 mg", forma: "tableta" |
| `VERAPAMILO TABLETAS RECUBIERTAS X 40 MG` | 🔴 Confuso "X 40" | "verapamilo", dosis: "40 mg", forma: "tableta recubierta" |
| `SILMAR` | 🔴 Incompleto, sin info | Necesita buscar en principioactivo |
| `RETNOL LOCIÓN` | ✅ Tiene forma | nombre: "retinol", forma: "loción" |
| `BEFLAVON GRAGEAS` | ⚠️ Mismo para múltiples presentaciones (10, 20, 30 uds) | Todos igual en descripcioncomercial |
| `FENOPRON 300 MG CAPSULAS.` | ✅ Bueno | nombre: "fenopron", dosis: "300 mg", forma: "cápsula" |
| `ORAVAX (CLORPROMAZINA ITALMEX 25 MG)` | ⚠️ Parentéticos confusos | Extraer "oravax", dosis: "25 mg" |
| `DORMICUM® AMPOLLAS 15MG/3ML` | 🔴 Símbolo ®, dosis/volumen confuso | "dormicum", dosis: "15 mg/3 ml", forma: "ampolla" |
| `VALCOTE ® 500 MG TABLETAS DE LIBERACION RETARDADA` | 🔴 Muy largo, tiene tipo de liberación | nombre: "valcote", dosis: "500 mg", forma: "tableta", tipo: "liberación retardada" |
| `FLUOXETINA 20 MG CÁPSULAS` | ✅ Muy bueno | nombre: "fluoxetina", dosis: "20 mg", forma: "cápsula" |

---

## 🔴 PROBLEMAS IDENTIFICADOS

### 1️⃣ **Información dispar y sin estructura**
- Algunos tienen: `NOMBRE + DOSIS + FORMA` (Ibuprofeno 500 MG tabletas)
- Otros tienen: `NOMBRE + FORMA` sin dosis (Retnol loción)
- Otros solo: `NOMBRE` (Silmar)
- Otros: `NOMBRE (alternativo) DOSIS` (Oravax - Clorpromazina)

### 2️⃣ **Símbolos especiales no removidos**
- `DORMICUM®` → sigue siendo `dormicum®` en nombre_limpio
- `VALCOTE ®` → sigue siendo `valcote ®`
- Afecta búsquedas y display

### 3️⃣ **Palabras clave de forma dispersas**
En algunos está en `producto`, en otros en `formafarmaceutica`:
- Producto: `"IBUPROFENO 500 MG TABLETAS"`
- formafarmaceutica: `"TABLETA"` (redundante)

### 4️⃣ **Dosis inconsistentes o confusas**
- `"VERAPAMILO X 40 MG"` → ¿40 unidades o 40 mg?
- `"DORMICUM 15MG/3ML"` → dosis + volumen juntos
- Columna `concentracion` tiene valor real (40, 15) pero mezcla en producto

### 5️⃣ **Información de presentación ausente en producto**
- `"BEFLAVON GRAGEAS"` aparece igual para 10, 20, 30, 100 grageas
- La cantidad está en `descripcioncomercial` ("CAJA POR 10 GRAGEAS", etc)
- No se puede distinguir la presentación desde `nombre_limpio`

### 6️⃣ **Información adicional de tipo de liberación**
- `"VALCOTE ® TABLETAS DE LIBERACION RETARDADA"`
- Tipo de liberación importante para medicamentos pero no separado

---

## ✅ PROPUESTA DE NORMALIZACIÓN (OPCIÓN C)

### **En Base de Datos: Crear estructura clara**

```python
class Medicamento:
    # CAMPOS A CREAR/MEJORAR:
    nombre_comercial: str  # "fluoxetina"
    dosis: str | None      # "20 mg"
    forma_farmaceutica: str  # "cápsula" (usar campo existente)
    presentacion: str | None  # "Caja x 10" (extraer de descripcioncomercial)
    tipo_liberacion: str | None  # "retardada" (para VALCOTE, etc)
    marca_comercial: str | None  # "DORMICUM" (si existe)

    # CAMPOS EXISTENTES A USAR:
    principio_activo: str  # "fluoxetina pura"
    laboratorio: str  # empresa
    atc: str  # categoría
    via_administracion: str  # oral, inyectable, etc
```

### **Proceso de normalización SQL**

```sql
-- 1. Limpiar símbolos especiales
SELECT
  regexp_replace(producto, '[®™©]', '', 'g') AS product_limpio

-- 2. Extraer dosis (patrón: número + mg/ml/%)
SELECT
  (regexp_matches(producto, '\d+(?:\.\d+)?\s?(mg|ml|UI|%|mcg|ug|mEq)', 'i'))[1] AS dosis

-- 3. Extraer forma de presentación
SELECT
  CASE
    WHEN producto ILIKE '%TABLETA%' THEN 'tableta'
    WHEN producto ILIKE '%CAPSULA%' THEN 'cápsula'
    WHEN producto ILIKE '%AMPOLLA%' THEN 'ampolla'
    WHEN producto ILIKE '%VIAL%' THEN 'vial'
    WHEN producto ILIKE '%JARABE%' THEN 'jarabe'
    WHEN producto ILIKE '%LOCION%' THEN 'loción'
    WHEN producto ILIKE '%GRAGEA%' THEN 'gragea'
    ELSE formafarmaceutica  -- fallback al campo existente
  END AS forma_normalizada

-- 4. Extraer nombre base (remover números y forma)
SELECT
  lower(trim(
    regexp_replace(
      regexp_replace(
        -- Remover dosis
        regexp_replace(producto, '\d+(?:\.\d+)?\s?(mg|ml|UI|%|mcg|ug|mEq)', '', 'i'),
        -- Remover formas
        '(TABLETA|CAPSULA|AMPOLLA|VIAL|JARABE|LOCION|GRAGEA|RECUBIERTA|RETARDADA)', '', 'i'
      ),
      -- Remover símbolos especiales
      '[®™©\(\)]+', '', 'g'
    )
  )) AS nombre_base
```

### **Migraciones necesarias**

1. **Crear columna `dosis`**
   ```sql
   ALTER TABLE medicamentos ADD COLUMN dosis VARCHAR;
   ```

2. **Crear columna `presentacion`**
   ```sql
   ALTER TABLE medicamentos ADD COLUMN presentacion VARCHAR;
   ```

3. **Crear columna `tipo_liberacion`**
   ```sql
   ALTER TABLE medicamentos ADD COLUMN tipo_liberacion VARCHAR;
   ```

4. **Mejorar `nombre_limpio`**
   - Usar SQL de arriba para normalizar
   - Remover símbolos ®™©
   - Remover números y dosis
   - Remover formas redundantes

---

## 📦 FRONT-END: Componente Card mejorado

Con datos normalizados:

```jsx
// Componente Card de medicamento
<article>
  {/* Header con nombre y dosis */}
  <div className="flex items-baseline gap-2">
    <h3 className="text-lg font-bold">{med.nombre_comercial}</h3>
    {med.dosis && <span className="text-sm text-slate-500">{med.dosis}</span>}
  </div>

  {/* Secundarios: forma y liberación */}
  <div className="flex gap-2 mt-2">
    <span className="badge bg-blue-100">{med.forma_farmaceutica}</span>
    {med.tipo_liberacion && (
      <span className="badge bg-purple-100">{med.tipo_liberacion}</span>
    )}
  </div>

  {/* Principio activo */}
  <p className="text-sm text-slate-500 mt-2">
    Activo: <strong>{med.principio_activo}</strong>
  </p>

  {/* Laboratorio */}
  <p className="text-xs text-slate-400 mt-1">{med.laboratorio}</p>

  {/* Presentación si existe */}
  {med.presentacion && (
    <p className="text-xs text-slate-400 mt-1">Presentación: {med.presentacion}</p>
  )}
</article>
```

---

## 🎯 RESUMEN DE CAMBIOS

### En DB (backend):
- ✅ Crear 3 columnas nuevas: `dosis`, `presentacion`, `tipo_liberacion`
- ✅ Mejorar limpieza de `nombre_limpio` (remover símbolos, dosis, forma)
- ✅ Crear funciones SQL para extracción consistente

### En Frontend:
- ✅ Diseñar card con campos separados
- ✅ Display más limpio y profesional
- ✅ Mejor búsqueda y filtrado

### Resultado final:
```
ANTES:
"paracetamol 500mg acetaminofén"  ← Confuso

DESPUÉS:
Paracetamol | 500mg | Tableta | Acetaminofén ← Claro
```
