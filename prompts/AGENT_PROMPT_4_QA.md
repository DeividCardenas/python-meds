# PROMPT 4: QA/TESTING AGENT
## VALIDATION & TESTING

You are a QA/Testing Agent. Your task is to validate that all 3 agents completed their work correctly.

### PREREQUISITE
✅ Backend-DB Agent completed
✅ Backend-Code Agent completed
✅ Frontend Agent completed

### OBJECTIVE
Validate complete medicamentos normalization implementation across all layers.

---

## TEST 1: DATABASE LAYER VALIDATION

### Test 1.1: Column Existence

**Execute**:
```sql
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'medicamentos'
ORDER BY column_name;
```

**Verify**: Output includes all 8 new columns:
- [ ] nombre_comercial
- [ ] marca_comercial
- [ ] dosis_cantidad (type: double precision or similar)
- [ ] dosis_unidad (type: character varying)
- [ ] via_administracion
- [ ] presentacion
- [ ] tipo_liberacion
- [ ] volumen_solucion

### Test 1.2: Index Existence

**Execute**:
```sql
SELECT indexname
FROM pg_indexes
WHERE tablename = 'medicamentos'
AND indexname LIKE 'ix_medicamentos%';
```

**Verify**: Output includes 3 indexes:
- [ ] ix_medicamentos_nombre_comercial
- [ ] ix_medicamentos_dosis
- [ ] ix_medicamentos_via

### Test 1.3: Data Population

**Execute**:
```sql
SELECT COUNT(*) total,
       COUNT(nombre_comercial) with_nombre,
       COUNT(dosis_cantidad) with_dosis,
       COUNT(via_administracion) with_via,
       COUNT(presentacion) with_presentacion,
       COUNT(forma_farmaceutica) with_forma
FROM medicamentos;
```

**Verify**:
- [ ] with_nombre >= 80 (80% of total)
- [ ] with_dosis >= 80
- [ ] with_via >= 90
- [ ] with_presentacion >= 75
- [ ] with_forma = 100 (should all be populated)

### Test 1.4: Data Quality Sample

**Execute**:
```sql
SELECT id_cum, nombre_comercial, dosis_cantidad, dosis_unidad,
       forma_farmaceutica, via_administracion, presentacion
FROM medicamentos
WHERE nombre_comercial IS NOT NULL
LIMIT 5;
```

**Verify**:
- [ ] nombre_comercial contains only letters/spaces (no numbers, no ®™)
- [ ] dosis_cantidad is numeric (e.g., 50.0, 15.5)
- [ ] dosis_unidad is valid (mg, ml, g, UI, %, mcg, ug, mEq)
- [ ] forma_farmaceutica is normalized lowercase
- [ ] via_administracion is lowercase
- [ ] presentacion follows format (e.g., "Caja x 30", "Blister x 10")

### Test 1.5: No Data Loss

**Execute**:
```sql
SELECT COUNT(*) total,
       COUNT(nombre_limpio) with_nombre_limpio,
       COUNT(laboratorio) with_laboratorio,
       COUNT(principio_activo) with_principio
FROM medicamentos;
```

**Verify**:
- [ ] All counts should match total (existing fields untouched)
- [ ] nombre_limpio still populated
- [ ] laboratorio still populated
- [ ] principio_activo still populated

---

## TEST 2: BACKEND API VALIDATION

### Test 2.1: GraphQL Schema Introspection

**Execute**:
```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ __type(name: \"Medicamento\") { fields { name type { name kind } } } }"}'
```

**Verify** response includes fields:
- [ ] nombreComercial: String (or String!)
- [ ] dosisCanitidad: Float
- [ ] dosisUnidad: String
- [ ] viaAdministracion: String
- [ ] presentacion: String
- [ ] tipoLiberacion: String

### Test 2.2: GraphQL Query Test

**Execute**:
```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query { buscarMedicamentos(texto: \"paracetamol\") { id idCum nombreComercial dosisCanitidad dosisUnidad viaAdministracion presentacion principioActivo } }"
  }'
```

**Verify**:
- [ ] Response is valid JSON
- [ ] No errors in response
- [ ] Response includes searched medication
- [ ] All requested fields present in response
- [ ] Data looks correct (dosis_cantidad is number, via is text, etc)

### Test 2.3: Python Model Validation

**Execute**:
```bash
cd backend
python -c "
from app.models.medicamento import Medicamento
m = Medicamento
fields = [f for f in dir(m) if not f.startswith('_')]
required_fields = ['nombre_comercial', 'dosis_cantidad', 'dosis_unidad',
                   'via_administracion', 'presentacion', 'tipo_liberacion']
for field in required_fields:
    assert hasattr(m, field), f'Missing field: {field}'
print('✅ All fields present in model')
"
```

**Verify**: Output shows "✅ All fields present in model"

---

## TEST 3: FRONTEND VALIDATION

### Test 3.1: Component Renders

**Action**: Browser at http://localhost:3000

1. Open component
2. Search for "paracetamol" (or any medication)
3. Verify:
   - [ ] Page loads without errors
   - [ ] Search results appear
   - [ ] Card titles visible
   - [ ] No red errors in console

### Test 3.2: Visual Inspection

**Action**: Look at rendered cards

Check each element:
- [ ] **Nombre**: Shows medication name (not including dose/form)
- [ ] **Dosis**: Shows as "50 mg" format on second line
- [ ] **Forma badge**: Blue badge with "Tableta" or similar
- [ ] **Vía badge**: Green badge with "Oral" or "Intravenosa"
- [ ] **Liberación badge**: Purple badge if applicable (not always present)
- [ ] **Principio activo**: Gray text showing active ingredient
- [ ] **Laboratorio**: With building icon
- [ ] **Presentación**: Shows "Caja x 30" format if available
- [ ] **Precio**: Shows in COP format if available
- [ ] **Button**: "Ver comparativa" button visible

### Test 3.3: Data Completeness

**Action**: Search for 5 different medications, verify:

For each result:
- [ ] Nombre shown
- [ ] Dosis shown (if available)
- [ ] Forma badge present
- [ ] Vía badge present (green)
- [ ] Principio activo shown
- [ ] Laboratorio shown
- [ ] No "undefined" values visible

### Test 3.4: Browser Console

**Action**: Open DevTools (F12) → Console tab

While scrolling through results:
- [ ] No JavaScript errors (red X symbols)
- [ ] No warning messages about missing props
- [ ] No GraphQL error messages

### Test 3.5: Network Validation

**Action**: DevTools → Network tab

Perform search:
1. Look for GraphQL request (labeled "graphql" or "operations")
2. Click it
3. View Response:
   - [ ] Valid JSON
   - [ ] No error field
   - [ ] All fields present in data

### Test 3.6: Responsive Design

**Action**: Browser DevTools → Device toolbar (mobile view)

- [ ] Cards stack properly on mobile
- [ ] Text readable on small screens
- [ ] Badges wrap correctly
- [ ] Button clickable
- [ ] No horizontal scroll

---

## TEST 4: END-TO-END WORKFLOW

### Test 4.1: Complete User Flow

**Action**: Simulate real user:

1. Open app at http://localhost:3000
2. Type "ibuprofen" in search box
3. Click "Buscar" button
4. Wait for results
5. Observe first card:
   - [ ] Medication name displays
   - [ ] Dose displays
   - [ ] Form badge visible
   - [ ] Via badge visible
   - [ ] All details populated
6. Click "Ver comparativa"
7. Verify modal opens with pricing comparison

**Expected**: Smooth flow, no errors, all data displays

### Test 4.2: Multiple Search Test

**Action**: Search for 3 different medications:

For each search:
- [ ] Results appear
- [ ] Cards format correctly
- [ ] Dose units consistent (mg, ml, etc)
- [ ] Via values consistent (oral, intravenous, etc)
- [ ] No duplicate displays

### Test 4.3: Empty Results Handling

**Action**: Search for nonsense: "xyzabc123"

- [ ] No errors
- [ ] "No hay resultados" message appears
- [ ] Component doesn't crash

---

## TEST 5: PERFORMANCE VALIDATION

### Test 5.1: Query Performance

**Execute**:
```sql
EXPLAIN ANALYZE
SELECT * FROM medicamentos
WHERE nombre_comercial ILIKE '%paracetamol%'
OR laboratorio ILIKE '%paracetamol%';
```

**Verify**:
- [ ] Execution uses indexes (Bitmap Index Scan or Index Scan visible)
- [ ] Execution time < 100ms for small dataset
- [ ] Planning time < 10ms

### Test 5.2: Frontend Load Time

**Action**: Browser Network tab, reload page

- [ ] Initial load < 3 seconds
- [ ] GraphQL query < 1 second
- [ ] Components render smooth (no jank)

---

## TEST 6: ERROR SCENARIOS

### Test 6.1: Missing Backend

**Action**: Stop backend server

Frontend behavior:
- [ ] No crash
- [ ] Error message appears (or loading spinner)
- [ ] Graceful degradation

### Test 6.2: Null Field Handling

**Action**: Verify medicines with missing fields display correctly

For medicine with NULL dosis_cantidad:
- [ ] No "undefined" shown
- [ ] Dose section doesn't render or empty
- [ ] Card still displays other fields

For medicine with NULL presentacion:
- [ ] Presentación line not shown
- [ ] Card still complete

### Test 6.3: Special Characters

**Action**: Search for medication with ® or ™ in name

- [ ] Renders without errors
- [ ] Symbols not in nombre_comercial
- [ ] marca_comercial contains symbol if applicable

---

## COMPLETION CHECKLIST

database:
- [ ] All 8 columns exist
- [ ] All 3 indexes exist
- [ ] 80%+ of key fields populated
- [ ] Sample data looks correct
- [ ] No data loss in existing fields

BACKEND API:
- [ ] GraphQL introspection shows new fields
- [ ] GraphQL query returns data correctly
- [ ] Python model loads without errors
- [ ] All mappings correct (no type mismatches)

FRONTEND:
- [ ] Component renders without errors
- [ ] All visual elements display correctly
- [ ] Console has no errors
- [ ] Network request includes all fields
- [ ] Responsive design works

END-TO-END:
- [ ] Complete user flow works
- [ ] Multiple searches work
- [ ] Error cases handled gracefully
- [ ] Performance acceptable

## SUCCESS CRITERIA

✅ All database validations pass
✅ All backend API tests pass
✅ All frontend visual tests pass
✅ All end-to-end workflows successful
✅ No console errors
✅ No database errors
✅ No network errors
✅ Performance acceptable (<1s queries)

## FINAL REPORT

```
VALIDATION REPORT: Medicamentos Normalization
===============================================

DATABASE:      ✅ PASS (8 cols, 3 idx, 85% populated)
BACKEND:       ✅ PASS (GraphQL schema, models working)
FRONTEND:      ✅ PASS (Component renders, no errors)
END-TO-END:    ✅ PASS (User flow works)
PERFORMANCE:   ✅ PASS (<100ms queries)

RESULT: ✅ READY FOR PRODUCTION

Issues found: [NONE / list if any]
```

---

**REPORT**: Submit validation report with one of:
- ✅ PASS: All tests successful, ready for production
- ⚠️ ISSUES: Some tests failed, provide details
- ❌ CRITICAL: Major issues found, requires fixes
