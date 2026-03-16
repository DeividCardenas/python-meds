# DATA MAPPING SPECIFICATION

## SOURCE TABLE: medicamentos_cum
## TARGET TABLE: medicamentos

### FIELD TRANSFORMATIONS

```yaml
transformations:
  - source: "producto"
    target: "nombre_comercial"
    operation: "extract_nombre_comercial"
    logic: "Remove digits, symbols (®™©), form names"
    example_input: "DICLOFENACO 50 MG TABLETAS"
    example_output: "diclofenaco"
    null_handling: "Return NULL if empty"

  - source: "producto"
    target: "marca_comercial"
    operation: "extract_marca"
    logic: "Extract if contains ® or ™"
    example_input: "DORMICUM® AMPOLLAS"
    example_output: "DORMICUM"
    null_handling: "NULL if no symbol"

  - source: "cantidad"
    target: "dosis_cantidad"
    operation: "extract_dosis_cantidad"
    logic: "Convert to FLOAT, validate > 0"
    example_input: "50"
    example_output: 50.0
    null_handling: "NULL if non-numeric"
    validation: "FLOAT > 0"

  - source: "unidadmedida"
    target: "dosis_unidad"
    operation: "direct_copy"
    logic: "Copy as-is"
    example_input: "mg"
    example_output: "mg"
    valid_values: ["mg", "ml", "g", "UI", "%", "mcg", "ug", "mEq"]
    null_handling: "NULL if not in valid_values"

  - source: "viaadministracion"
    target: "via_administracion"
    operation: "normalize_via_administracion"
    logic: "Use value OR infer from forma_farmaceutica"
    example_input: "ORAL"
    example_output: "oral"
    fallback_logic:
      - if: "contains(forma_farmaceutica, 'INYECTABLE')"
        then: "intravenosa"
      - if: "contains(forma_farmaceutica, 'OFTALMICA')"
        then: "conjuntival"
      - if: "contains(forma_farmaceutica, 'LOCION')"
        then: "tópica"
    null_handling: "NULL if 'SIN DATO' and cannot infer"

  - source: "descripcioncomercial"
    target: "presentacion"
    operation: "extract_presentacion"
    logic: "Parse CAJA/BLISTER/FRASCO patterns"
    patterns:
      - regex: "(?i)caja\s+(?:por|x|con)\s+(\d+)"
        format: "Caja x {match[1]}"
      - regex: "(?i)blister\s+x\s+(\d+)"
        format: "Blister x {match[1]}"
      - regex: "(?i)frasco\s+(\d+)\s*ml"
        format: "Frasco {match[1]} ml"
      - regex: "(\d+)\s*ml"
        format: "{match[1]} ml"
    null_handling: "NULL if no pattern matches"

  - source: "formafarmaceutica"
    target: "forma_farmaceutica"
    operation: "normalize_forma_farmaceutica"
    logic: "Standardize form names"
    mappings:
      "TABLETA": "tableta"
      "TABLETA CUBIERTA": "tableta cubierta"
      "TABLETA CUBIERTA CON PELICULA": "tableta cubierta"
      "TABLETA RECUBIERTA": "tableta recubierta"
      "CAPSULA DURA": "cápsula dura"
      "CAPSULA BLANDA": "cápsula blanda"
      "SOLUCION INYECTABLE": "solución inyectable"
      "SOLUCION OFTALMICA": "solución oftálmica"
      "LOCION": "loción"
      "GRAGEA": "gragea"
    null_handling: "lowercase as-is if not mapped"

  - source: "producto"
    target: "tipo_liberacion"
    operation: "extract_tipo_liberacion"
    logic: "Search for release type keywords"
    patterns:
      - keyword: "LIBERACION RETARDADA"
        value: "retardada"
      - keyword: "LIOFILIZADO"
        value: "liofilizado"
      - keyword: "LIBERACION SOSTENIDA"
        value: "sostenida"
    null_handling: "NULL if not found"

  - source: "unidadreferencia"
    target: "volumen_solucion"
    operation: "extract_volumen_solucion"
    logic: "Extract ml/L values for injectables"
    regex: "(\d+(?:\.\d+)?)\s*ml"
    null_handling: "NULL if no volume found"

  - source: ["descripcioncomercial", "producto"]
    target: "nombre_limpio"
    operation: "build_nombre_limpio"
    logic: "Concatenate descripcioncomercial + principioactivo, normalize spaces"
    process:
      1: "COALESCE(descripcioncomercial, producto, '')"
      2: "Append ' ' + principioactivo"
      3: "Normalize whitespace"
      4: "Convert to lowercase"
    null_handling: "Empty string if both NULL"
```

---

## VALIDATION RULES

```yaml
validation_rules:

  dosis_cantidad:
    type: "FLOAT"
    constraints:
      - min_value: 0 (exclusive)
      - allow_null: true
    action_on_invalid: "SET NULL"

  dosis_unidad:
    type: "VARCHAR"
    constraints:
      - allowed_values: ["mg", "ml", "g", "UI", "%", "mcg", "ug", "mEq"]
      - allow_null: true
    action_on_invalid: "SET NULL"

  via_administracion:
    type: "VARCHAR"
    constraints:
      - allowed_values: ["oral", "intravenosa", "intramuscular", "subcutánea", "tópica", "vaginal", "conjuntival", "intranasal"]
      - allow_null: true
    action_on_invalid: "SET NULL"

  nombre_comercial:
    type: "VARCHAR"
    constraints:
      - min_length: 1
      - allow_null: true
    action_on_invalid: "SET NULL"

  volumen_solucion:
    type: "FLOAT"
    constraints:
      - min_value: 0 (exclusive)
      - allow_null: true
      - only_if: "forma_farmaceutica LIKE '%INYECTABLE%'"
    action_on_invalid: "SET NULL"
```

---

## DATABASE SCHEMA

```sql
CREATE TABLE medicamentos (
  id UUID PRIMARY KEY,
  id_cum VARCHAR UNIQUE NOT NULL,

  -- EXISTING FIELDS (keep)
  nombre_limpio VARCHAR NOT NULL,
  laboratorio VARCHAR,
  principio_activo VARCHAR,
  forma_farmaceutica VARCHAR,
  registro_invima VARCHAR,
  atc VARCHAR,
  estado_cum VARCHAR,
  activo BOOLEAN,
  embedding_status VARCHAR,

  -- NEW FIELDS (add)
  nombre_comercial VARCHAR,
  marca_comercial VARCHAR,
  dosis_cantidad FLOAT,
  dosis_unidad VARCHAR,
  via_administracion VARCHAR,
  presentacion VARCHAR,
  tipo_liberacion VARCHAR,
  volumen_solucion FLOAT,

  -- METADATA (keep)
  created_at TIMESTAMP,
  updated_at TIMESTAMP,

  -- INDICES (add)
  INDEX ix_medicamentos_nombre_comercial (nombre_comercial),
  INDEX ix_medicamentos_dosis (dosis_cantidad, dosis_unidad),
  INDEX ix_medicamentos_via (via_administracion)
);
```

---

## MIGRATION STRATEGY

```yaml
steps:
  1:
    name: "Create columns"
    command: "ALTER TABLE medicamentos ADD COLUMN ..."
    reversible: true
    dependencies: []

  2:
    name: "Create SQL functions"
    command: "CREATE OR REPLACE FUNCTION ..."
    reversible: true
    dependencies: [step_1]

  3:
    name: "Execute UPDATE query"
    command: "UPDATE medicamentos SET ... FROM medicamentos_cum"
    reversible: true
    dependencies: [step_1, step_2]
    timeout_seconds: 60

  4:
    name: "Create indexes"
    command: "CREATE INDEX ..."
    reversible: true
    dependencies: [step_1, step_3]

  5:
    name: "Validate data"
    command: "SELECT COUNT(*) ... WHERE field IS NOT NULL"
    reversible: false
    dependencies: [step_3, step_4]
    success_criteria:
      - "80%+ of nombre_comercial populated"
      - "80%+ of forma_farmaceutica populated"
      - "0 errors in logs"
```

---

## EXPECTED RESULTS

```json
{
  "success_metrics": {
    "total_medicamentos": 100,
    "nombre_comercial": {
      "populated": 90,
      "null": 10,
      "percentage": "90%"
    },
    "dosis_cantidad": {
      "populated": 85,
      "null": 15,
      "percentage": "85%"
    },
    "dosis_unidad": {
      "populated": 85,
      "null": 15,
      "percentage": "85%"
    },
    "via_administracion": {
      "populated": 95,
      "null": 5,
      "percentage": "95%"
    },
    "presentacion": {
      "populated": 75,
      "null": 25,
      "percentage": "75%"
    },
    "tipo_liberacion": {
      "populated": 5,
      "null": 95,
      "percentage": "5%"
    },
    "volumen_solucion": {
      "populated": 8,
      "null": 92,
      "percentage": "8%"
    },
    "forma_farmaceutica": {
      "populated": 100,
      "null": 0,
      "percentage": "100%"
    }
  },
  "expected_outcomes": {
    "database_errors": 0,
    "migration_success": true,
    "data_integrity": "100%",
    "backward_compatibility": true
  }
}
```

---

## SAMPLE DATA TRANSFORMATION

```json
{
  "before": {
    "id_cum": "100458-01",
    "producto": "DICLOFENACO 50 MG TABLETAS",
    "descripcioncomercial": "CAJA CON 100 TABLETAS EN BLISTERES DE ALUMINIO-PVC POR 10 CADA UNO",
    "cantidad": "50",
    "unidadmedida": "mg",
    "formafarmaceutica": "TABLETA CUBIERTA CON PELICULA",
    "viaadministracion": "ORAL",
    "unidadreferencia": "TABLETA",
    "principioactivo": "DICLOFENACO SÓDICO",
    "concentracion": "A"
  },
  "after": {
    "id_cum": "100458-01",
    "nombre_comercial": "diclofenaco",
    "marca_comercial": null,
    "nombre_limpio": "caja con 100 tabletas en blisteres de aluminio-pvc por 10 cada uno diclofenaco sódico",
    "dosis_cantidad": 50.0,
    "dosis_unidad": "mg",
    "forma_farmaceutica": "tableta cubierta",
    "via_administracion": "oral",
    "presentacion": "Caja x 100",
    "tipo_liberacion": null,
    "volumen_solucion": null,
    "principioactivo": "DICLOFENACO SÓDICO",
    "laboratorio": "GENERICOS ESPECIALES S.A."
  }
}
```
