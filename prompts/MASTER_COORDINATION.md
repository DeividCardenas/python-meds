# MASTER COORDINATION PROMPT
## FOR PARALLEL AGENT EXECUTION

Use this prompt to coordinate multiple agents working on medicamentos normalization.

---

## OVERVIEW

This is a 4-phase project requiring 4 different agents working in sequence with opportunity for parallelization:

```
Phase 1 (Backend-DB):    Database migration + SQL functions        [5-10 min]
Phase 2 (Backend-Code):  Python models + GraphQL (parallel OK)     [10-15 min]
Phase 3 (Frontend):      React components (must wait for Phase 2)   [10-15 min]
Phase 4 (QA/Testing):    Validation (final, after all phases)       [10-15 min]

SEQUENTIAL REQUIREMENT:
  Phase 1 ──→ Phase 2 ──→ Phase 3 ──→ Phase 4
             (can do 2&3 in parallel after 1)

TOTAL TIME: ~35-50 minutes
PARALLEL OPTIMIZATION: Backend-DB → (Backend-Code + Frontend in parallel) → QA
OPTIMIZED TIME: ~25-35 minutes
```

---

## AGENT ASSIGNMENT

```
Agent 1: Backend-DB Agent
├─ Task: Database migration + SQL functions
├─ Document: AGENT_PROMPT_1_DB.md
├─ Duration: 5-10 minutes
├─ Report: "DB Phase Complete - Ready for Backend-Code"
└─ Success: Migration executed, 8 columns created, 7 functions working

Agent 2: Backend-Code Agent
├─ Task: Python models + GraphQL schema
├─ Document: AGENT_PROMPT_2_CODE.md
├─ Duration: 10-15 minutes
├─ Report: "Backend-Code Phase Complete - Ready for Frontend"
└─ Success: Model updated, GraphQL schema compiles, mapper updated

Agent 3a: Frontend Agent (starts after Agent 2)
├─ Task: React component + GraphQL query
├─ Document: AGENT_PROMPT_3_FRONTEND.md
├─ Duration: 10-15 minutes
├─ Report: "Frontend Phase Complete - Ready for QA"
└─ Success: Component renders, no errors, all fields display

Agent 4: QA/Testing Agent (starts after all others)
├─ Task: Comprehensive validation
├─ Document: AGENT_PROMPT_4_QA.md
├─ Duration: 10-15 minutes
├─ Report: "Validation Complete - PASS/FAIL"
└─ Success: All tests pass, no errors, ready for production
```

---

## EXECUTION FLOW

### Timeline: Parallel Execution

```
Time 0:00  ├─ Start: Agent-DB (AGENT_PROMPT_1_DB.md)
Time 0:10  │  ├─ DB Phase Complete ✅
Time 0:10  │  ├─ Start: Agent-Backend-Code (AGENT_PROMPT_2_CODE.md)
Time 0:10  │  └─ Agent-Code can work in parallel
Time 0:10  │     ├─ Start: Agent-Frontend (AGENT_PROMPT_3_FRONTEND.md)
Time 0:10  │     │  (Frontend waits for Backend-Code to finish)
Time 0:25  │     ├─ Backend-Code Complete ✅
Time 0:25  │     └─ Frontend Phase Complete ✅
Time 0:25  │
Time 0:25  └─ Start: Agent-QA (AGENT_PROMPT_4_QA.md)
Time 0:40  └─ QA Phase Complete ✅

TOTAL: ~40 minutes (optimized from 50+ sequential)
```

---

## STEP-BY-STEP INSTRUCTIONS

### Step 1: Send to Backend-DB Agent

**Instruction**:
```
Execute AGENT_PROMPT_1_DB.md completely:
1. Create Alembic migration file
2. Execute migration
3. Create all 7 SQL functions
4. Run UPDATE query
5. Verify with validation queries
6. Report success when complete
```

**Wait for**: Agent reports "DB Phase Complete"

---

### Step 2: Send to Backend-Code Agent

**After Step 1 completes**, send:

**Instruction**:
```
Execute AGENT_PROMPT_2_CODE.md completely:
1. Update Medicamento model (8 new fields)
2. Update GraphQL type
3. Update GraphQL mapper
4. Verify schema compilation
5. Test with sample query
6. Report success when complete
```

**Parallel**: Can also start Frontend agent at same time (it will wait for GraphQL completion)

---

### Step 3: Send to Frontend Agent

**Can start after Step 2 begins, but must wait for Step 2 completion**

**Instruction**:
```
Execute AGENT_PROMPT_3_FRONTEND.md completely:
1. Update GraphQL query with 8 new fields
2. Replace card JSX with new version
3. Test in browser
4. Verify data flow
5. Test edge cases
6. Report success when complete
```

**Prerequisite**: Step 2 (Backend-Code) must be complete

---

### Step 4: Send to QA Agent

**After Steps 2 & 3 complete**, send:

**Instruction**:
```
Execute AGENT_PROMPT_4_QA.md completely:
1. Validate database layer (columns, indexes, data)
2. Validate backend API (GraphQL, models)
3. Validate frontend (component, console, network)
4. Run end-to-end workflow tests
5. Test performance
6. Test error scenarios
7. Generate validation report
```

**Report format**:
```
✅ PASS: All validations successful, ready for production
  - Database: [summary]
  - Backend: [summary]
  - Frontend: [summary]
  - E2E: [summary]
```

---

## SUCCESS CRITERIA BY PHASE

### Phase 1: Backend-DB (Agent 1)
```
✅ Migration file created and executed
✅ 8 new columns in medicamentos table
✅ 3 indexes created (nombre_comercial, dosis, via)
✅ 7 SQL functions created
✅ UPDATE query completed
✅ 80%+ of fields populated
✅ Validation queries return expected results
```

### Phase 2: Backend-Code (Agent 2)
```
✅ Medicamento model has 8 new fields
✅ GraphQL type updated with 8 fields
✅ Mapper includes all 8 field mappings
✅ GraphQL schema compiles without errors
✅ Introspection query returns new fields
✅ Sample query executes and returns data
```

### Phase 3: Frontend (Agent 3)
```
✅ GraphQL query includes 8 new fields
✅ Card JSX updated with new layout
✅ Component renders without errors
✅ All visual elements display correctly
✅ Browser console shows no errors
✅ Network request includes all fields
✅ Responsive design works
```

### Phase 4: QA (Agent 4)
```
✅ All database validations pass
✅ All backend API tests pass
✅ All frontend visual tests pass
✅ All end-to-end workflows successful
✅ Performance acceptable
✅ Error scenarios handled gracefully
✅ Validation report generated
```

---

## COMMUNICATION TEMPLATE

### For Agent 1 (Backend-DB)
```
Your prompt: AGENT_PROMPT_1_DB.md

Follow all steps sequentially:
1. CREATE migration
2. EXECUTE migration
3. CREATE SQL functions
4. EXECUTE UPDATE
5. VERIFY with validation queries

When complete, report:
"DB Phase Complete: 8 columns created, 7 functions working, X% populated"
```

### For Agent 2 (Backend-Code)
```
Your prompt: AGENT_PROMPT_2_CODE.md
PREREQUISITE: Agent-DB must have completed

Follow all steps:
1. UPDATE model (8 fields + indexes)
2. UPDATE GraphQL type
3. UPDATE mapper
4. VERIFY schema compiles
5. TEST with sample query

When complete, report:
"Backend-Code Phase Complete: Model + GraphQL + Mapper updated"
```

### For Agent 3 (Frontend)
```
Your prompt: AGENT_PROMPT_3_FRONTEND.md
PREREQUISITE: Agent-Code must have completed Phase 2

Follow all steps:
1. UPDATE GraphQL query (8 new fields)
2. REPLACE card JSX
3. TEST in browser
4. VERIFY data flow
5. TEST edge cases

When complete, report:
"Frontend Phase Complete: Component renders, all fields display"
```

### For Agent 4 (QA)
```
Your prompt: AGENT_PROMPT_4_QA.md
PREREQUISITE: All other agents must complete

Execute all 6 tests:
TEST 1: Database layer validation
TEST 2: Backend API validation
TEST 3: Frontend validation
TEST 4: End-to-end workflow
TEST 5: Performance
TEST 6: Error scenarios

When complete, report validation status:
✅ PASS / ⚠️ ISSUES / ❌ CRITICAL
```

---

## QUICK REFERENCE: AGENT CONTACTS

Agent 1 (Database):
- Prompt file: AGENT_PROMPT_1_DB.md
- Estimated time: 5-10 min
- Start after: NONE (first phase)
- Report template: "DB Phase Complete"

Agent 2 (Backend Code):
- Prompt file: AGENT_PROMPT_2_CODE.md
- Estimated time: 10-15 min
- Start after: Agent 1 complete
- Report template: "Backend-Code Phase Complete"

Agent 3 (Frontend):
- Prompt file: AGENT_PROMPT_3_FRONTEND.md
- Estimated time: 10-15 min
- Start after: Agent 2 complete
- Report template: "Frontend Phase Complete"

Agent 4 (QA):
- Prompt file: AGENT_PROMPT_4_QA.md
- Estimated time: 10-15 min
- Start after: ALL agents complete
- Report template: "Validation Complete: [PASS/ISSUES/CRITICAL]"

---

## DOCUMENTS LOCATION

All agent prompts in:
`C:\Users\Dillan\.claude\projects\c--Users-Dillan-Music-python-meds\memory\`

Files:
- AGENT_PROMPT_1_DB.md ← Database & SQL
- AGENT_PROMPT_2_CODE.md ← Python & GraphQL
- AGENT_PROMPT_3_FRONTEND.md ← React & Query
- AGENT_PROMPT_4_QA.md ← Validation & Testing

---

## FAILURE RECOVERY

If any agent reports issues:

1. **Database failures**: Run downgrade, fix migration, retry
2. **Backend failures**: Check type mismatches, syntax errors, retry
3. **Frontend failures**: Check GraphQL response, component syntax, retry
4. **Testing failures**: Identify specific failing test, report to responsible agent

---

## FINAL WORKFLOW

```
SEND TO AGENT 1:
└─ AGENT_PROMPT_1_DB.md
   WAIT FOR: "DB Phase Complete"

SEND TO AGENT 2:
└─ AGENT_PROMPT_2_CODE.md
   (Can start 3 in parallel)

SEND TO AGENT 3:
└─ AGENT_PROMPT_3_FRONTEND.md
   WAIT FOR: Agent 2 + Agent 3 complete

SEND TO AGENT 4:
└─ AGENT_PROMPT_4_QA.md
   WAIT FOR: Validation report

FINAL STATUS:
└─ ✅ All complete → Ready for production
   ⚠️ Issues → Fix and retest
   ❌ Critical → Rollback and investigate
```

---

**EXECUTION READY** ✅

All 4 agent prompts are self-contained and ready to send.
No additional context needed - each agent has everything required to complete their phase.
