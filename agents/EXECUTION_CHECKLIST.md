# EXECUTION CHECKLIST FOR AGENTS

## PHASE 1: DATABASE MIGRATION

```
TASK: Create and execute Alembic migration

SUBTASKS:
  [ ] SYNC: Read AGENT_INSTRUCTIONS.md PHASE 1
  [ ] GENERATE: Create migration file: backend/alembic/versions/[DATE]_[XXXX]_add_medicamento_normalization_fields.py
  [ ] POPULATE: Copy upgrade() function from AGENT_INSTRUCTIONS.md
  [ ] POPULATE: Copy downgrade() function from AGENT_INSTRUCTIONS.md
  [ ] EXECUTE: Run `alembic upgrade head`
  [ ] VERIFY: Check no errors in migration output
  [ ] CONFIRM: Query: SELECT column_name FROM information_schema.columns WHERE table_name='medicamentos' AND column_name IN ('nombre_comercial', 'dosis_cantidad', ...)
  [ ] CONFIRM: All 8 columns exist

EXPECTED OUTPUT:
  - Migration file created successfully
  - Database updated without errors
  - 8 new columns visible in medicamentos table
  - 3 indexes created

ROLLBACK PROCEDURE:
  Command: `alembic downgrade -1`
  Expected: All 8 columns removed
```

---

## PHASE 2: SQL FUNCTIONS & DATA POPULATION

```
TASK: Create normalization functions and populate data

SUBTASKS:
  [ ] READ: AGENT_INSTRUCTIONS.md PHASE 2 - Full text
  [ ] READ: DATA_MAPPING_SPEC.md - Understanding transformations
  [ ] CREATE: Copy 7 functions to SQL file: backend/sql/normalize_medicamentos_campos.sql
  [ ] VERIFY: Syntax check all functions
  [ ] EXECUTE: Create functions in database

  [ ] EXECUTE: Run UPDATE query to populate medicamentos from medicamentos_cum
  [ ] MONITOR: Wait for query completion (expected: < 10 seconds for 100 rows)
  [ ] VERIFY: No SQL errors in execution

  [ ] EXECUTE: Validation queries from AGENT_INSTRUCTIONS.md
  [ ] ANALYZE: Results:
      - Total medicamentos: ___
      - With nombre_comercial: ___ (target: 85%+)
      - With dosis_cantidad: ___ (target: 80%+)
      - With via_administracion: ___ (target: 90%+)
  [ ] CONFIRM: 80%+ of key fields populated

EXPECTED OUTPUT:
  - All 7 SQL functions created
  - UPDATE query completed
  - Sample SELECT shows correct transformations
  - Data validation passes minimum thresholds

ERROR HANDLING:
  - If function creation fails: Check syntax in AGENT_INSTRUCTIONS.md
  - If UPDATE fails: Check medicamentos_cum table exists and has data
  - If validation fails: Run SELECT with problematic fields to debug
```

---

## PHASE 3: PYTHON MODEL UPDATE

```
TASK: Update Medicamento SQLModel

SUBTASKS:
  [ ] OPEN: backend/app/models/medicamento.py
  [ ] LOCATE: Class definition: class Medicamento(SQLModel, table=True)
  [ ] READ: AGENT_INSTRUCTIONS.md PHASE 3
  [ ] ADD: 8 new Field() items to class (copy from AGENT_INSTRUCTIONS.md)
  [ ] ADD: 3 Index() items to __table_args__ tuple
  [ ] VERIFY: No duplicate field names
  [ ] VERIFY: All fields have Optional[type] or type
  [ ] SYNTAX CHECK: Python linting passes

EXPECTED OUTPUT:
  - Model compiles without errors
  - All 8 new fields accessible as attributes
  - Indexes defined in __table_args__
  - No breaking changes to existing fields

TESTING:
  Command: `python -c "from app.models.medicamento import Medicamento; print(Medicamento.__fields__.keys())"`
  Expected: All field names including new ones
```

---

## PHASE 4: GRAPHQL SCHEMA UPDATE

```
TASK: Update GraphQL types and mappers

SUBTASKS:
  [ ] OPEN: backend/app/graphql/types/medicamento.py
  [ ] READ: AGENT_INSTRUCTIONS.md PHASE 4
  [ ] UPDATE: Medicamento type - add 8 new fields
  [ ] VERIFY: All fields have Optional[type] wrapper
  [ ] VERIFY: No duplicate field names
  [ ] SYNTAX CHECK: Python imports correct (strawberry, Optional, datetime)

  [ ] OPEN: backend/app/graphql/mappers/medicamento.py
  [ ] READ: mapear_medicamento() function
  [ ] UPDATE: Add 8 new mappings in return statement
  [ ] VERIFY: Each DB field mapped to GraphQL field
  [ ] VERIFY: Field names match Medicamento type definition
  [ ] SYNTAX CHECK: No missing commas or parentheses

  [ ] COMPILE: GraphQL schema generation
  [ ] VERIFY: No schema compilation errors
  [ ] QUERY_TEST: GraphQL introspection includes new fields

EXPECTED OUTPUT:
  - GraphQL type includes all 8 new fields
  - Mapper correctly transforms DB model to GraphQL type
  - Schema compiles successfully
  - Test query can request new fields

ERROR HANDLING:
  - Field type mismatch: Check Float vs String in both files
  - Missing imports: Add `from typing import Optional`
  - Schema errors: Run GraphQL validation tool
```

---

## PHASE 5: FRONTEND COMPONENT UPDATE

```
TASK: Update React BuscadorMedicamentos component

SUBTASKS:
  [ ] OPEN: frontend/src/components/BuscadorMedicamentos.tsx
  [ ] LOCATE: Card component (around line 302-350)
  [ ] READ: AGENT_INSTRUCTIONS.md PHASE 5
  [ ] BACKUP: Create copy of original component
  [ ] REPLACE: Article JSX with new version from AGENT_INSTRUCTIONS.md
  [ ] VERIFY: All classNames are valid TailwindCSS classes
  [ ] VERIFY: All variables (item.field names) match GraphQL response

  [ ] UPDATE: GraphQL query (SearchMedicamentosDocument)
  [ ] ADD: 8 new fields to query fragment
  [ ] VERIFY: Field names in camelCase match GraphQL schema
  [ ] VERIFY: GraphQL query compiles without errors

  [ ] SYNTAX CHECK: TypeScript linting passes
  [ ] BUILD CHECK: `npm run build` (if available)
  [ ] LOCAL TEST: `npm run dev` and view in browser

EXPECTED OUTPUT:
  - Component renders without errors
  - Card displays all new fields correctly
  - Query fetches new fields from backend
  - CSS/layout looks correct
  - No console errors

TESTING:
  - [ ] Search for a medication
  - [ ] Verify card shows: nombre_comercial, dosis, forma, via, presentacion
  - [ ] Verify badges render for via_administracion, tipo_liberacion
  - [ ] Verify no missing values (check console for undefined)
  - [ ] Verify responsive design on mobile
```

---

## VALIDATION PHASE

```
TASK: Comprehensive validation of complete implementation

DATABASE VALIDATION:
  [ ] Query: SELECT COUNT(*) FROM medicamentos WHERE nombre_comercial IS NOT NULL
      Expected: >= 80 (for 100 total)
  [ ] Query: SELECT COUNT(*) FROM medicamentos WHERE dosis_cantidad IS NOT NULL
      Expected: >= 80 (for 100 total)
  [ ] Query: SELECT * FROM medicamentos LIMIT 5
      Verify: All new fields present and populated correctly

BACKEND VALIDATION:
  [ ] Python: `python -m pytest tests/models/test_medicamento.py` (if exists)
      Expected: All tests pass
  [ ] GraphQL: Query medicamentos via GraphQL endpoint
      Expected: All fields returned, no null schema errors
  [ ] API: Test endpoint with sample query
      Verify: Response includes nombre_comercial, dosis_cantidad fields

FRONTEND VALIDATION:
  [ ] npm run dev
  [ ] Open browser: http://localhost:3000
  [ ] Search for medication (e.g., "paracetamol")
  [ ] Verify:
      [ ] Card displays new fields
      [ ] Dosis shown correctly
      [ ] Badges render (forma, via, liberacion)
      [ ] No console errors
      [ ] No network 500 errors
  [ ] Test filtering by via_administracion (if filter exists)
  [ ] Test responsive layout on mobile

DATA INTEGRITY VALIDATION:
  [ ] No NULL values where shouldn't be (excepting expected NULLs like tipo_liberacion)
  [ ] No data loss from original medicamentos fields
  [ ] nombre_limpio field still populated correctly
  [ ] All indices created and functional
  [ ] Query performance acceptable (< 100ms for search)

MIGRATION VALIDATION:
  [ ] Test rollback: `alembic downgrade -1`
      Expected: All 8 columns removed
  [ ] Restore: `alembic upgrade head`
      Expected: Columns recreated, data repopulated

FINAL CHECKLIST:
  [ ] All 8 columns exist in DB
  [ ] All 7 SQL functions created
  [ ] 80%+ of medicamentos populated
  [ ] Python model updated
  [ ] GraphQL schema updated
  [ ] Frontend displays new fields
  [ ] No console errors
  [ ] No database errors
  [ ] All tests pass
  [ ] Backward compatible (existing fields unchanged)
  [ ] Can rollback cleanly
```

---

## POST-DEPLOYMENT MONITORING

```
TASK: Monitor implementation post-deployment

WEEKLY CHECKS:
  [ ] Database query performance (check slow logs)
  [ ] Error logs for any normalization failures
  [ ] User feedback on card display
  [ ] Frontend performance metrics

DATA QUALITY CHECKS:
  [ ] Monthly: Verify data still normalized correctly
  [ ] Check for any NULL anomalies in key fields
  [ ] Validate new medicamentos follow same rules
  [ ] Audit any manual corrections

OPTIMIZATION CHECKS:
  [ ] Index usage (are indices being used?)
  [ ] Query plan for search queries
  [ ] Cache hit rates (if applicable)
  [ ] Frontend bundle size increase
```

---

## DOCUMENTS REFERENCE MAP

| Phase | Task | Document | Section |
|-------|------|----------|---------|
| 1 | Database migration | AGENT_INSTRUCTIONS.md | PHASE 1 |
| 2 | SQL functions | AGENT_INSTRUCTIONS.md | PHASE 2 |
| 2 | Data mapping | DATA_MAPPING_SPEC.md | All |
| 3 | Model update | AGENT_INSTRUCTIONS.md | PHASE 3 |
| 4 | GraphQL | AGENT_INSTRUCTIONS.md | PHASE 4 |
| 5 | Frontend | AGENT_INSTRUCTIONS.md | PHASE 5 |
| All | Validation | AGENT_INSTRUCTIONS.md | VALIDATION CHECKLIST |

---

## FAILURE RECOVERY

```
IF Migration fails:
  1. Run: alembic downgrade -1
  2. Fix migration file
  3. Re-run: alembic upgrade head

IF SQL functions fail:
  1. Check syntax in AGENT_INSTRUCTIONS.md
  2. Run each function separately
  3. Debug with sample inputs

IF UPDATE fails:
  1. Verify medicamentos_cum table exists
  2. Check for data type mismatches
  3. Run validation queries to identify problem rows
  4. Fix problematic data manually if needed
  5. Re-run UPDATE for remaining rows

IF Frontend breaks:
  1. Check TypeScript compilation errors
  2. Verify GraphQL query syntax
  3. Check API response format matches expectations
  4. Rollback component changes from git if needed

IF Tests fail:
  1. Check if tests need updating for new fields
  2. Verify test mocks include new fields
  3. Update test assertions if needed
```

---

## COMPLETION INDICATORS

```
SUCCESS: All items below checked

✅ DATABASE LEVEL:
  [x] Migration executed
  [x] 8 columns created
  [x] 3 indexes created
  [x] 7 SQL functions working
  [x] UPDATE query populated data
  [x] 80%+ of fields populated

✅ BACKEND LEVEL:
  [x] Model updated with 8 fields
  [x] GraphQL schema updated
  [x] Mappers return new fields
  [x] API endpoints working
  [x] No errors in logs

✅ FRONTEND LEVEL:
  [x] Component renders new fields
  [x] Query includes new fields
  [x] Card displays correctly
  [x] No console errors
  [x] Responsive design works

✅ TESTING LEVEL:
  [x] All unit tests pass
  [x] Integration tests pass
  [x] Manual testing completed
  [x] Edge cases tested
  [x] Rollback tested

✅ PRODUCTION READY:
  [x] Code reviewed
  [x] All tests pass
  [x] Performance acceptable
  [x] Documentation updated
  [x] Team trained
```
