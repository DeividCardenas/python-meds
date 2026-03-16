# Análisis de Estructura de Datos: Medicamentos y Medicamentos CUM

## 🔴 PROBLEMA ACTUAL

### Fuente de datos: `medicamentos_cum` (desde Socrata/INVIMA)
```
expediente: 123456
consecutivocum: 1
descripcioncomercial: "PARACETAMOL 500MG"  ← Nombre comercial con dosis
producto: "PARACETAMOL TABLETAS"
principioactivo: "ACETAMINOFÉN"
formafarmaceutica: "TABLETA"
titular: "LABORATORIO ABC"
registrosanitario: "INVIMA-2021M-001"
estadocum: "Vigente"
atc: "N02BE01"
```

### Construcción de `nombre_limpio` actual (línea 447-456 en `cum_socrata_service.py`):
```sql
lower(trim(
    regexp_replace(
        COALESCE(c.descripcioncomercial, c.producto, '')
            || ' '
            || COALESCE(c.principioactivo, ''),
        '\\s+', ' ', 'g'
    )
)) AS nombre_limpio
```

**Resultado:** `"paracetamol 500mg acetaminofén"`

### ❌ PROBLEMAS:

1. **Demasiado largo y redundante**
   - Concatena descripción comercial + principio activo
   - Ejemplo: "paracetamol 500mg acetaminofén" (34 caracteres)
   - En tarjeta se ve cortado y poco práctico

2. **No normaliza caracteres especiales**
   - `ASPIRIN® 500MG` → `"aspirin® 500mg"` (mantiene ®)
   - `COLCHICINA™` → `"colchicina™"` (mantiene ™)

3. **Incluye información redundante**
   - La dosis ya está en `descripcioncomercial`
   - El principio activo está mejor en campo separado `principio_activo`

4. **Estructura inconsistente**
   - A veces usa `descripcioncomercial`, a veces `producto`
   - Ambos pueden tener variaciones en formato

5. **No es SEO/search-friendly**
   - Todo mezclado hace búsquedas menos precisas
   - Buscar por dosis es difícil

---

## ✅ SOLUCIÓN PROPUESTA

### Opción A: Separar campos de forma estructurada

**Pasos:**
1. Mantener `nombre_limpio` solo con el nombre comercial (sin dosis, sin principio activo)
2. Crear campo separado `dosis` extrayendo de `descripcioncomercial`
3. Usar campos existentes: `principio_activo`, `forma_farmaceutica`, `laboratorio`

**Cambios en modelo:**
```python
# En Medicamento model
nombre_limpio: str  # "paracetamol" (solo nombre)
dosis: str | None   # "500mg" (extraído)
# Mantener existentes:
# principio_activo: "acetaminofén"
# forma_farmaceutica: "tableta"
# laboratorio: "laboratorio abc"
```

**Nueva construcción de `nombre_limpio`:**
```sql
-- Extraer solo nombre comercial (antes de la dosis)
lower(trim(regexp_replace(
    COALESCE(c.descripcioncomercial, c.producto, ''),
    '[®™]',  -- Remover símbolos de marca
    '',
    'g'
))) AS nombre_limpio,
-- O más agresivo: extraer solo palabras (sin números)
lower(trim(regexp_replace(
    COALESCE(c.descripcioncomercial, c.producto, ''),
    '[0-9®™\s/\-\.]+',  -- Remove numbers, special chars, dosis
    ' ',
    'g'
))) AS nombre_limpio
```

---

### Opción B: Usar componentes de display variables (recomendado para UI)

Mantener la BD igual, pero en **frontend** mostrar de forma inteligente:

**Componente Card mejorado:**
```jsx
// Título principal (corto)
<h3>{nombreLimpio}</h3>  // "Paracetamol"

// Dosis como badge
<span className="badge">{dosis}</span>  // "500mg"

// Principio activo en gris (secundario)
<p className="secondary">{principioActivo}</p>  // "Acetaminofén"

// Forma farmacéutica pequeña
<span className="small">{formaFarmaceutica}</span>  // "Tableta"
```

**Ventaja:** Sin cambiar BD, solo mejora UI

---

## 📊 DATOS A NORMALIZAR EN BD

Si vamos por **Opción A**, necesitamos:

```sql
-- Función para extraer dosis de descripción comercial
CREATE OR REPLACE FUNCTION extract_dosis(descripcion TEXT)
RETURNS TEXT AS $$
BEGIN
  -- Extrae patrones como "500mg", "10ml", "1000 UI", etc.
  RETURN (regexp_matches(descripcion, '\d+\s*(mg|ml|UI|g|mcg|ug|%|mEq)', 'i'))[1];
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Función para limpiar nombre comercial
CREATE OR REPLACE FUNCTION clean_nombre_comercial(texto TEXT)
RETURNS TEXT AS $$
BEGIN
  -- Remove: números, símbolos, espacios múltiples
  RETURN lower(trim(
    regexp_replace(
      regexp_replace(texto, '[®™©]', '', 'g'),  -- Símbolos marca
      '[0-9\-/\.\,]+', '', 'g'  -- Números y separadores
    )
  ));
END;
$$ LANGUAGE plpgsql IMMUTABLE;
```

---

## 🎯 RECOMENDACIÓN

**Mejor balance:** **Opción A + Opción B**

1. **En BD:** Criar campo `dosis` y mejorar limpieza de `nombre_limpio`
2. **En Frontend:** Diseñar tarjeta componiendo estos campos

**Beneficios:**
- ✅ Datos más estructurados
- ✅ Búsquedas más precisas
- ✅ UI más limpia y profesional
- ✅ Facilita análisis y reportes
