# Análisis Completo: Relaciones entre Columnas de medicamentos_cum

## 📊 EJEMPLOS REALES - ESTRUCTURA ACTUAL

### Ejemplo 1: DICLOFENACO (Medicamento Oral típico)
```
producto:               "DICLOFENACO 50 MG TABLETAS"
descripcioncomercial:   "CAJA CON 100 TABLETAS EN BLISTERES DE ALUMINIO-PVC POR 10 CADA UNO"
principioactivo:        "DICLOFENACO SÓDICO"
viaadministracion:      "ORAL"
concentracion:          "A"          ← PROBLEMA: "A" no es una dosis
unidadmedida:           "mg"
cantidad:               "50"         ← LA DOSIS REAL ESTÁ AQUÍ ❌
unidadreferencia:       "TABLETA"
formafarmaceutica:      "TABLETA CUBIERTA CON PELÍCULA"
```

### Ejemplo 2: DORMICUM® (Medicamento Inyectable)
```
producto:               "DORMICUM® AMPOLLAS 15MG/3ML"
descripcioncomercial:   "CAJA POR 5 AMPOLLAS POR 3 ML. DE VIDRIO TIPO I"
principioactivo:        "MIDAZOLAM"
viaadministracion:      "INTRAVENOSA"
concentracion:          "C"          ← Nuevo: "C" es código, no dosis
unidadmedida:           "mg"
cantidad:               "15"         ← Dosis del principio activo
unidadreferencia:       "AMPOLLA POR 3 ML"  ← Volumen adjunto ⚠️
formafarmaceutica:      "SOLUCION INYECTABLE"
```

### Ejemplo 3: RETNOL LOCIÓN (Medicamento Tópico)
```
producto:               "RETNOL LOCIÓN"
descripcioncomercial:   "CAJA CON UN FRASCO PET ÁMBAR POR 60 ML."
principioactivo:        "TRETINOINA (ÁCIDO RETINOICO)"
viaadministracion:      "TOPICA (EXTERNA)"
concentracion:          "B"          ← Código, no dosis útil
unidadmedida:           "g"
cantidad:               "0.05"       ← Dosis real
unidadreferencia:       "100 ML DE LOCIÓN"  ← Volumen de presentación
formafarmaceutica:      "LOCION"
```

### Ejemplo 4: BEFLAVON GRAGEAS (Múltiples presentaciones)
```
producto:               "BEFLAVON GRAGEAS"
descripcioncomercial:   "CAJA POR 10 GRAGEAS"  ← Varía (10, 20, 30, 100)
                        "CAJA POR 20 GRAGEAS"  ← Mismo producto, diferente presentación
                        "CAJA POR 30 GRAGEAS"
                        "CAJA POR 100 GRAGEAS"
principioactivo:        "AESCINA AMORFA"
viaadministracion:      "SIN DATO"
concentracion:          "S"
unidadmedida:           "mg"
cantidad:               "20"        ← Dosis por gragea
unidadreferencia:       "GRAGEA"
formafarmaceutica:      "TABLETA CUBIERTA (GRAGEA)"
```

### Ejemplo 5: SILMAR (Incompleto)
```
producto:               "SILMAR"
descripcioncomercial:   "CAJA POR 20 CAPSULAS"
principioactivo:        "SILIMARINA 100%"
viaadministracion:      "ORAL"
concentracion:          "A"
unidadmedida:           "mg"
cantidad:               "150"       ← Dosis sin dosis en producto
unidadreferencia:       "CAPSULAS"
formafarmaceutica:      "CAPSULA DURA"
```

---

## 🔴 PROBLEMAS IDENTIFICADOS

### 1️⃣ **concentracion NO es concentración**
```
Esperado: dosis como "50", "15", "300"
Realidad: códigos como "A", "B", "C", "S"

Significado desconocido:
  • A: 30 ocurrencias (¿Anormal? ¿Análisis?)
  • B: 5 ocurrencias
  • C: 8 ocurrencias
  • S: 4 ocurrencias
```
❌ **Esta columna es inútil para nuestros propósitos**

### 2️⃣ **cantidad vs unidadmedida vs unidadreferencia DESORGANIZADOS**

**Casos confusos:**
- DICLOFENACO: cantidad=50, unidadmedida=mg, unidadreferencia=TABLETA
  → ¿50 mg por qué unidad? ¿Por tableta?
  → SÍ, pero no está claro

- DORMICUM: cantidad=15, unidadmedida=mg, unidadreferencia=AMPOLLA POR 3 ML
  → 15 mg en 3 ml (concentración de solución = 5 mg/ml)
  → El volumen está en unidadreferencia, confuso

- RETNOL: cantidad=0.05, unidadmedida=g, unidadreferencia=100 ML DE LOCIÓN
  → 0.05 g es la dosis, pero en 100 ml = 0.05%
  → No hay relación clara entre cantidad y unidadreferencia

### 3️⃣ **Información de presentación dispersa**

Dónde está la cantidad de unidades en la caja:
```
❌ NO está en: cantidad, concentracion, unidadreferencia
✅ ESTÁ EN: descripcioncomercial como "CAJA POR 30", "CAJA X 50", "BLISTER X 10"

Ejemplo BEFLAVON:
  • descripcioncomercial: "CAJA POR 10 GRAGEAS"    ← Presentación
  • cantidad: "20"                                  ← Dosis por gragea
  • unidadreferencia: "GRAGEA"                     ← Unidad base

PROBLEMA: No puedo distinguir variantes sin parsear descripcioncomercial
```

### 4️⃣ **formafarmaceutica vs unidadreferencia REDUNDANTES**

```
formafarmaceutica:  "TABLETA"
unidadreferencia:   "TABLETA"        ← Repetido

formafarmaceutica:  "CAPSULA DURA"
unidadreferencia:   "POR CAPSULA"    ← Similar

formafarmaceutica:  "SOLUCION INYECTABLE"
unidadreferencia:   "AMPOLLA POR 3 ML"   ← Información adicional aquí

CONCLUSIÓN: formafarmaceutica es más confiable, unidadreferencia tiene contexto
```

### 5️⃣ **viaadministracion INCOMPLETA**

```
Encontrados:
  • ORAL
  • VAGINAL
  • TOPICA (EXTERNA)
  • INTRAVENOSA
  • CONJUNTIVAL
  • SIN DATO

PROBLEMA: "SIN DATO" debería inferirse de otros campos
```

### 6️⃣ **cantidadcum NO es cantidad de presentación**

```
"cantidadcum" = cantidad de reglas/presentaciones para el MISMO expediente

EJEMPLO: VERAPAMILO
  • Expediente: 10124
  • Consecutivos: 1, 2, 3, 4
  → 4 variantes (X50, X30, X100, X200 tabletas)
  → cantidadcum = 4 para todos

CAUSA: Mismo medicamento en diferentes presentaciones = diferentes CUMs
```

---

## ✅ MAPEO CORRECTO DE INFORMACIÓN

### **¿Qué información tenemos realmente?**

```
1. MEDICAMENTO (Problema: esparcido entre producto y otros)
   Fuente: producto + principioactivo
   Limpieza: De "DICLOFENACO 50 MG TABLETAS" extraer "DICLOFENACO"

2. DOSIS (Problema: en "cantidad", no en "concentracion")
   Fuente: cantidad + unidadmedida
   Valor: "50" + "mg" = "50 mg"
   Validación: cantidad debe ser número

3. FORMA FARMACÉUTICA (Correcto)
   Fuente: formafarmaceutica
   Ejemplos: TABLETA, CAPSULA, AMPOLLA, LOCION, etc.
   Backup: unidadreferencia si es necesario

4. VÍA DE ADMINISTRACIÓN (Incompleta)
   Fuente: viaadministracion
   Problemas: "SIN DATO" sin fallback

5. PRESENTACIÓN (Problema: en descripcioncomercial)
   Fuente: descripcioncomercial
   Patrón: "CAJA (POR|X|CON) (\d+)"
   Ejemplo: "CAJA POR 30 TABLETAS" → presentacion = "30 unidades"

6. INFORMACIÓN ADICIONAL (Esparcida)
   • Volumen (inyectables): unidadreferencia
   • Tipo de liberación: producto
   • Concentración de solución: unidadreferencia

7. INÚTIL (Ignorar)
   • concentracion (solo contiene A, B, C, S - códigos desconocidos)
   • (Posiblemente) cantidadcum (info administrativa)
```

---

## 🏗️ ESTRUCTURA MEJORADA PROPUESTA

### Tabla actual: medicamentos
```sql
CREATE TABLE medicamentos (
  id UUID PRIMARY KEY,
  id_cum VARCHAR UNIQUE NOT NULL,

  -- NOMBRE (mejorado)
  nombre_comercial VARCHAR NOT NULL,      -- "diclofenaco" (limpio, sin números)
  marca_comercial VARCHAR,                 -- "DORMICUM", "VALCOTE" (si existe)

  -- DOSIS Y FORMA (estructurado)
  dosis_cantidad FLOAT,                    -- 50, 15, 300
  dosis_unidad VARCHAR,                    -- "mg", "ml", "UI", "%", "g"
  forma_farmaceutica VARCHAR NOT NULL,    -- "tableta", "cápsula", "ampolla"
  tipo_forma_detalles VARCHAR,             -- "recubierta", "dura", "blanda", "liofilizado"

  -- VÍA Y PRESENTACIÓN
  via_administracion VARCHAR,              -- "oral", "intravenosa", "tópica"
  presentacion VARCHAR,                    -- "Caja x 30", "Frasco 60 ml"

  -- INFORMACIÓN ADICIONAL
  volumen_solucion FLOAT,                  -- Para inyectables: 3 ml en DORMICUM
  concentracion_solucion VARCHAR,          -- Para soluciones: "5 mg/ml"
  tipo_liberacion VARCHAR,                 -- "retardada", "normal"

  -- CLASIFICACIÓN
  principio_activo VARCHAR,                -- Existente
  laboratorio VARCHAR,                     -- Existente
  atc VARCHAR,                             -- Existente
  registro_invima VARCHAR,                 -- Existente

  -- ESTADO
  activo BOOLEAN,
  estado_cum VARCHAR,

  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

---

## 📋 REGLAS DE EXTRACCIÓN SQL

### **1. Nombre Comercial (de product)**
```sql
-- Remover dosis, forma, símbolos
lower(trim(
  regexp_replace(
    regexp_replace(
      regexp_replace(producto, '[®™©]', '', 'g'),        -- Símbolos
      '\d+\s*(mg|ml|ui|%|g|mcg).*', '', 'i'),           -- Dosis
      '(tableta|capsula|ampolla|vial|jarabe|locion|gragea|inyectable|solucion).*', '', 'i'  -- Forma
    )
  )
)) AS nombre_comercial
```

### **2. Dosis (de cantidad + unidadmedida)**
```sql
CASE
  WHEN cantidad ~ '^\d+\.?\d*$' AND unidadmedida IS NOT NULL
  THEN cantidad::FLOAT
  ELSE NULL
END AS dosis_cantidad,

unidadmedida AS dosis_unidad  -- "mg", "ml", etc
```

### **3. Forma Normalizada (de formafarmaceutica)**
```sql
CASE formafarmaceutica
  WHEN 'TABLETA' THEN 'tableta'
  WHEN 'TABLETA CUBIERTA' THEN 'tableta cubierta'
  WHEN 'TABLETA CUBIERTA (GRAGEA)' THEN 'tableta cubierta (gragea)'
  WHEN 'TABLETA CUBIERTA CON PELICULA' THEN 'tableta'
  WHEN 'TABLETA RECUBIERTA' THEN 'tableta recubierta'
  WHEN 'CAPSULA DURA' THEN 'cápsula dura'
  WHEN 'CAPSULA BLANDA' THEN 'cápsula blanda'
  WHEN 'SOLUCION INYECTABLE' THEN 'solución inyectable'
  WHEN 'SOLUCION OFTALMICA' THEN 'solución oftálmica'
  WHEN 'LOCION' THEN 'loción'
  ELSE lower(formafarmaceutica)
END AS forma_farmaceutica_normalizada
```

### **4. Presentación (de descripcioncomercial)**
```sql
-- Extraer "CAJA POR 30" o "CAJA X 100" o "BLISTER X 10"
CASE
  WHEN descripcioncomercial ~* 'caja\s+(por|x|con)\s+(\d+)'
  THEN 'Caja x ' || (regexp_matches(descripcioncomercial, 'caja\s+(?:por|x|con)\s+(\d+)', 'i'))[1]

  WHEN descripcioncomercial ~* 'blister\s+x\s+(\d+)'
  THEN 'Blister x ' || (regexp_matches(descripcioncomercial, 'blister\s+x\s+(\d+)', 'i'))[1]

  WHEN descripcioncomercial ~* '(\d+)\s+ml'
  THEN (regexp_matches(descripcioncomercial, '(\d+)\s+ml', 'i'))[1] || ' ml'

  ELSE descripcioncomercial
END AS presentacion
```

### **5. Volumen Solución (para inyectables)**
```sql
-- De "AMPOLLA POR 3 ML" o unidadreferencia
CASE
  WHEN unidadreferencia ~* '(\d+(?:\.\d+)?)\s*ml'
  THEN (regexp_matches(unidadreferencia, '(\d+(?:\.\d+)?)\s*ml', 'i'))[1]::FLOAT
  ELSE NULL
END AS volumen_solucion
```

### **6. Vía de Administración (validar y llenar)**
```sql
CASE
  WHEN viaadministracion IN ('ORAL', 'VAGINAL', 'TOPICA (EXTERNA)', 'INTRAVENOSA', 'CONJUNTIVAL')
  THEN lower(viaadministracion)

  WHEN viaadministracion = 'SIN DATO' AND formafarmaceutica ILIKE '%INYECTABLE%'
  THEN 'intravenosa'

  WHEN viaadministracion = 'SIN DATO' AND formafarmaceutica ILIKE '%OFTALMICA%'
  THEN 'conjuntival'

  ELSE 'no especificada'
END AS via_administracion_normalizada
```

### **7. Tipo de Liberación**
```sql
CASE
  WHEN producto ILIKE '%LIBERACION RETARDADA%'
  THEN 'retardada'

  WHEN producto ILIKE '%LIOFILIZADO%'
  THEN 'liofilizado'

  ELSE NULL
END AS tipo_liberacion
```

---

## 📊 EJEMPLO DE TRANSFORMACIÓN

### ENTRADA (CSV):
```
producto: "VALCOTE ® 500 MG TABLETAS DE LIBERACION RETARDADA"
descripcioncomercial: "CAJA CON FRASCO POR 30 TABLETAS CUBIERTAS"
principioactivo: "DIVALPROATO SODICO EQUIVALENTE A 500MG"
cantidad: "538.1"
unidadmedida: "mg"
formafarmaceutica: "TABLETA CUBIERTA CON PELICULA"
viaadministracion: "ORAL"
```

### SALIDA (Normalizado):
```
nombre_comercial: "valcote"
marca_comercial: "VALCOTE"
dosis_cantidad: 500
dosis_unidad: "mg"
forma_farmaceutica: "tableta cubierta"
tipo_forma_detalles: "película"
via_administracion: "oral"
presentacion: "Caja x 30"
tipo_liberacion: "retardada"
principio_activo: "divalproato sódico"
```

---

## 🎯 SIGUIENTE: FRONTEND

Con estructura limpia:
```jsx
<article>
  <h3>Valcote <span className="text-sm">500 mg</span></h3>
  <div className="flex gap-2">
    <badge>Tableta cubierta</badge>
    <badge>Retardada</badge>
  </div>
  <p className="text-sm">Oral · Divalproato sódico</p>
  <p className="text-xs text-gray-500">Caja x 30</p>
</article>
```

---

## ✅ RESUMEN DE ACCIÓN

1. **Crear 6 columnas nuevas** en medicamentos
2. **Crear 7 funciones SQL** de normalización
3. **Ejecutar UPDATE masivo** poblando datos
4. **Actualizar modelos** en Python (SQLModel)
5. **Actualizar GraphQL** types y queries
6. **Mejorar Frontend** con nueva estructura
