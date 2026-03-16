# AGENT ROUTING INDEX

## PURPOSE
Direct AI agents to correct documentation based on task type.

---

## ROUTING LOGIC

```
IF task_type == "database_migration":
  -> AGENT_INSTRUCTIONS.md (PHASE 1)
  -> EXECUTION_CHECKLIST.md (DATABASE MIGRATION)

IF task_type == "sql_functions":
  -> AGENT_INSTRUCTIONS.md (PHASE 2)
  -> DATA_MAPPING_SPEC.md
  -> EXECUTION_CHECKLIST.md (PHASE 2)

IF task_type == "python_model":
  -> AGENT_INSTRUCTIONS.md (PHASE 3)
  -> EXECUTION_CHECKLIST.md (PHASE 3)

IF task_type == "graphql_update":
  -> AGENT_INSTRUCTIONS.md (PHASE 4)
  -> EXECUTION_CHECKLIST.md (PHASE 4)

IF task_type == "frontend_component":
  -> AGENT_INSTRUCTIONS.md (PHASE 5)
  -> EXECUTION_CHECKLIST.md (PHASE 5)

IF task_type == "data_validation":
  -> DATA_MAPPING_SPEC.md
  -> AGENT_INSTRUCTIONS.md (VALIDATION CHECKLIST)

IF task_type == "rollback":
  -> AGENT_INSTRUCTIONS.md (ROLLBACK PROCEDURE)
  -> EXECUTION_CHECKLIST.md (FAILURE RECOVERY)

IF task_type == "monitoring":
  -> EXECUTION_CHECKLIST.md (POST-DEPLOYMENT MONITORING)

IF question == "What should I do next?":
  -> AGENT_INSTRUCTIONS.md (start at current UNCHECKED phase)

IF question == "Did I complete successfully?":
  -> EXECUTION_CHECKLIST.md (COMPLETION INDICATORS)

IF question == "How to recover from error?":
  -> EXECUTION_CHECKLIST.md (FAILURE RECOVERY)
```

---

## DOCUMENT DEPENDENCIES

```
AGENT_INSTRUCTIONS.md (root document)
├─ PHASE 1: Database (must complete first)
│  └─ requires: PostgreSQL, Alembic
│  └─ outputs: migration file, 8 new columns
│
├─ PHASE 2: SQL Functions (must complete after PHASE 1)
│  └─ requires: migration from PHASE 1
│  └─ references: DATA_MAPPING_SPEC.md
│  └─ outputs: 7 functions, populated data
│
├─ PHASE 3: Python Model (must complete after PHASE 1)
│  └─ requires: migration from PHASE 1
│  └─ outputs: updated Medicamento class
│
├─ PHASE 4: GraphQL (must complete after PHASE 3)
│  └─ requires: PHASE 3 model
│  └─ outputs: updated schema, mappers
│
└─ PHASE 5: Frontend (must complete after PHASE 4)
   └─ requires: PHASE 4 GraphQL
   └─ outputs: updated component, query

EXECUTION_CHECKLIST.md (parallel document)
├─ Provides checkboxes for each phase
├─ References AGENT_INSTRUCTIONS.md sections
├─ Includes validation queries
└─ Includes failure recovery

DATA_MAPPING_SPEC.md (reference document)
├─ explains every field transformation
├─ provides validation rules
├─ shows example inputs/outputs
└─ referenced by PHASE 2
```

---

## PARALLEL EXECUTION STRATEGY

```
SEQUENTIAL REQUIRED:
  PHASE 1 -> PHASE 2 -> PHASES 3,4,5 (can do 3,4,5 in parallel)

Example timeline:

Agent-DB starts:          Agent-Backend starts simultaneously:  Agent-Frontend waits:
  PHASE 1 ✓               PHASE 3 (reading model structure)      [waiting for PHASE 4]
  PHASE 2 ✓               PHASE 4 (updating GraphQL)
                          ✓ PHASES 3&4 done → sends to Frontend

                                                                  Agent-Frontend starts:
                                                                  PHASE 5 ✓

TOTAL TIME: Sum of longest path (PHASE 1 + PHASE 2 + PHASE 4)
NOT: Sum of all phases
```

---

## INFORMATION RETRIEVAL PATTERNS

### Pattern 1: "Show me the SQL for field X"
```
1. Query DATA_MAPPING_SPEC.md -> transformations -> [field name]
2. Extract: source, target, operation, logic
3. Use operation name to find function in AGENT_INSTRUCTIONS.md PHASE 2
4. Return function code + usage example
```

### Pattern 2: "What should field X contain?"
```
1. Query DATA_MAPPING_SPEC.md -> transformations -> [field name]
2. Extract: example_input, example_output
3. Check validation_rules for constraints and valid_values
4. Return specification
```

### Pattern 3: "Is my transformation correct?"
```
1. Compare output against DATA_MAPPING_SPEC.md examples
2. Run validation_rules checks
3. Verify with AGENT_INSTRUCTIONS.md function logic
4. Return: VALID or identify errors
```

### Pattern 4: "How do I update component X?"
```
1. Query AGENT_INSTRUCTIONS.md PHASE [X]
2. Extract file path and code section
3. Get detailed instructions from EXECUTION_CHECKLIST.md
4. Return step-by-step instructions
```

### Pattern 5: "Check my progress"
```
1. Identify current phase from user input
2. Go to EXECUTION_CHECKLIST.md -> [PHASE NAME]
3. Show unchecked items
4. Return: completed items + next items
```

---

## AGENT COMMANDS

### Structure for agent tasks:
```
COMMAND: medicamentos_normalize
PHASE: 2
TASK: create_sql_functions
ACTION: create
FILE: backend/sql/normalize_medicamentos_campos.sql
REFERENCE: AGENT_INSTRUCTIONS.md:PHASE 2:Functions
VALIDATION: EXECUTION_CHECKLIST.md:PHASE 2:Validation
EXPECTED_DURATION: 5 minutes
ERROR_RECOVERY: EXECUTION_CHECKLIST.md:FAILURE RECOVERY:If SQL functions fail
```

---

## ERROR CLASSIFICATION & ROUTING

```
ERROR: "Alembic migration failed"
  -> EXECUTION_CHECKLIST.md -> FAILURE RECOVERY -> "IF Migration fails"
  -> AGENT_INSTRUCTIONS.md -> PHASE 1 -> Syntax check

ERROR: "UPDATE query exceeded timeout"
  -> EXECUTION_CHECKLIST.md -> FAILURE RECOVERY -> "IF UPDATE fails"
  -> DATA_MAPPING_SPEC.md -> Check data types
  -> More memory/longer timeout needed

ERROR: "GraphQL schema validation failed"
  -> EXECUTION_CHECKLIST.md -> PHASE 4 -> SYNTAX CHECK
  -> AGENT_INSTRUCTIONS.md -> PHASE 4 -> Check field mapping

ERROR: "Frontend card not rendering"
  -> EXECUTION_CHECKLIST.md -> PHASE 5 -> TESTING section
  -> Check browser console
  -> Verify GraphQL query returns data

ERROR: "80% population threshold not met"
  -> EXECUTION_CHECKLIST.md -> PHASE 2 -> Analyze Results
  -> DATA_MAPPING_SPEC.md -> Check transformation logic
  -> Review beispiele in AGENT_INSTRUCTIONS.md
```

---

## QUICK REFERENCE: COMMAND EXAMPLES

```
Query: "Create migration for medicamentos"
Action: Go to AGENT_INSTRUCTIONS.md PHASE 1, copy code, execute

Query: "Show me transformation for nombre_comercial"
Action: Go to DATA_MAPPING_SPEC.md, find transformations.nombre_comercial

Query: "Validate my SQL function"
Action: Compare against DATA_MAPPING_SPEC.md validation_rules

Query: "What's next after PHASE 2?"
Action: Suggest PHASE 3, provide AGENT_INSTRUCTIONS.md PHASE 3 link

Query: "How to rollback?"
Action: Show AGENT_INSTRUCTIONS.md ROLLBACK PROCEDURE

Query: "I got error X"
Action: Look up in EXECUTION_CHECKLIST.md FAILURE RECOVERY

Query: "Am I done?"
Action: Show EXECUTION_CHECKLIST.md COMPLETION INDICATORS, verify all checked
```

---

## DOCUMENT METRICS

```
AGENT_INSTRUCTIONS.md:
  - Lines: ~400
  - Sections: 5 PHASES + VALIDATION + ROLLBACK
  - Code blocks: 15+
  - SQL functions: 7
  - Python code: 3 blocks
  - JSX code: 1 block
  - Read time for agent: 2-3 minutes (per phase)
  - Execution time estimate: 30 seconds - 5 minutes (per phase)

DATA_MAPPING_SPEC.md:
  - Lines: ~250
  - Transformations: 8 (one per field)
  - Validation rules: 5
  - Sample transformations: 1+ per field
  - Reference time: 1-2 minutes
  - Schema definition: 1 SQL block

EXECUTION_CHECKLIST.md:
  - Lines: ~350
  - Checklists: 7 (one per phase + validation + monitoring + recovery)
  - Subtasks per phase: 5-10
  - Verification steps: 50+
  - Check time: 1 minute per phase
  - Total execution tracking: 30 minutes
```

---

## AUTOMATED WORKFLOW EXAMPLE

```
Agent receives task: "Implement medicamentos normalization"

1. Read: AGENT_INSTRUCTIONS.md (overview)
   Time: 3 min
   Decision: "I need to do 5 phases - let me break down"

2. Execute PHASE 1:
   - Reference: AGENT_INSTRUCTIONS.md PHASE 1:DATABASE MIGRATION
   - Checklist: EXECUTION_CHECKLIST.md PHASE 1:DATABASE MIGRATION
   - Execute: Create migration file
   - Verify: Run `alembic upgrade head`
   - Time: 5 min

3. Execute PHASE 2:
   - Reference: AGENT_INSTRUCTIONS.md PHASE 2:SQL NORMALIZATION
   - Reference: DATA_MAPPING_SPEC.md:all
   - Checklist: EXECUTION_CHECKLIST.md PHASE 2:SQL FUNCTIONS
   - Execute: Create 7 functions
   - Execute: Run UPDATE query
   - Verify: Validation queries
   - Time: 15 min

4. Execute PHASE 3:
   - Reference: AGENT_INSTRUCTIONS.md PHASE 3:PYTHON MODEL
   - Checklist: EXECUTION_CHECKLIST.md PHASE 3:PYTHON MODEL
   - Execute: Add 8 fields to Medicamento class
   - Verify: Syntax check, imports
   - Time: 5 min

5. Execute PHASE 4:
   - Reference: AGENT_INSTRUCTIONS.md PHASE 4:GRAPHQL
   - Checklist: EXECUTION_CHECKLIST.md PHASE 4:GRAPHQL
   - Execute: Update GraphQL type
   - Execute: Update mapper
   - Verify: Schema compilation
   - Time: 10 min

6. Execute PHASE 5:
   - Reference: AGENT_INSTRUCTIONS.md PHASE 5:FRONTEND
   - Checklist: EXECUTION_CHECKLIST.md PHASE 5:FRONTEND
   - Execute: Update component
   - Execute: Update query
   - Verify: `npm run dev`, visual check
   - Time: 15 min

7. Validate all:
   - Reference: AGENT_INSTRUCTIONS.md VALIDATION CHECKLIST
   - Checklist: EXECUTION_CHECKLIST.md VALIDATION PHASE
   - Database queries
   - Backend tests
   - Frontend tests
   - Time: 10 min

TOTAL: ~55 minutes for one agent
With parallel execution (Agent-DB + Agent-Backend + Agent-Frontend): ~20-25 minutes
```

---

## SUCCESS CRITERIA

Agent has successfully completed task when:

```
✅ PHASE 1: [ ] Migration file created [ ] alembic upgrade head succeeded
✅ PHASE 2: [ ] 7 functions created [ ] UPDATE query completed [ ] 80%+ populated
✅ PHASE 3: [ ] Model updated [ ] 8 fields added [ ] Python syntax valid
✅ PHASE 4: [ ] GraphQL type updated [ ] Mapper updated [ ] Schema compiles
✅ PHASE 5: [ ] Component updated [ ] Query updated [ ] Renders without errors
✅ VALIDATION: [ ] All DB queries pass [ ] Frontend displays correctly [ ] No errors
```

If any [ ] is NOT checked → Task incomplete, continue or debug
If ALL are checked → Task complete, report success
