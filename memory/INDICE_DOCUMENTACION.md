# 📚 ÍNDICE DE DOCUMENTACIÓN - Normalización de Medicamentos

**Última actualización:** 16 de Marzo 2026
**Status:** Listo para distribución

---

## 🎯 GUÍA DE LECTURA POR ROL

### 👨‍💼 **MANAGER / Product Owner**
**Tiempo de lectura:** 10 minutos
**Prioridad:** ALTA

📄 **Documentos a leer:**
1. Este archivo (2 min)
2. `RESUMEN_EJECUTIVO.md` (8 min)

**¿Qué obtendrás?**
- Contexto completo del proyecto
- Timeline de implementación
- Métricas de éxito
- Checklist de validación

---

### 👨‍💻 **BACKEND ENGINEER**
**Tiempo de lectura:** 45 minutos
**Tiempo de implementación:** 3-4 horas
**Prioridad:** ALTA

📄 **Documentos a leer:**
1. `RESUMEN_EJECUTIVO.md` (5 min)
2. `PROMPTS_IMPLEMENTACION.md` → PROMPTS 1 y 2 (20 min)
3. `COMANDOS_LISTOS_EJECUTAR.md` → STEPS 1 y 2 (20 min)

**¿Qué harás?**
- [ ] Crear migration Alembic
- [ ] Crear 7 SQL functions
- [ ] Ejecutar UPDATE masivo
- [ ] Validar datos

**Archivos a modificar:**
- `backend/alembic/versions/` (CREAR)
- `backend/sql/` (CREAR)
- `backend/app/models/medicamento.py` (MODIFICAR)

**Preguntas que resolverán los docs:**
- "¿Cómo extraigo nombre sin dosis?" → PROMPTS_IMPLEMENTACION.md PROMPT 2, función 1
- "¿Cuál es el SQL exacto?" → COMANDOS_LISTOS_EJECUTAR.md PASO 2
- "¿Cómo valido después?" → COMANDOS_LISTOS_EJECUTAR.md final, sección VERIFICACIÓN

---

### 🎨 **FRONTEND ENGINEER**
**Tiempo de lectura:** 30 minutos
**Tiempo de implementación:** 2-3 horas
**Prioridad:** ALTA

📄 **Documentos a leer:**
1. `RESUMEN_EJECUTIVO.md` (5 min)
2. `ANALISIS_COLUMNAS_RELACIONADAS.md` → Ejemplos (15 min)
3. `COMANDOS_LISTOS_EJECUTAR.md` → PASO 5 (10 min)

**¿Qué harás?**
- [ ] Actualizar componente card
- [ ] Actualizar GraphQL query
- [ ] Probar en navegador

**Archivos a modificar:**
- `frontend/src/components/BuscadorMedicamentos.tsx` (~200 líneas)

**Preguntas que resolverán los docs:**
- "¿Cómo se ve una tarjeta mejorada?" → ANALISIS_COLUMNAS_RELACIONADAS.md, sección FRONTEND
- "¿Cuál es el JSX exacto?" → COMANDOS_LISTOS_EJECUTAR.md PASO 5
- "¿Qué campos pido al GraphQL?" → Mismo lugar, sección GraphQL Query

---

### 🔍 **DBA / DevOps**
**Tiempo de lectura:** 20 minutos
**Prioridad:** MEDIA

📄 **Documentos a leer:**
1. `RESUMEN_EJECUTIVO.md` → Sección "DATOS DE REFERENCIA" (5 min)
2. `COMANDOS_LISTOS_EJECUTAR.md` → PASO 2 SQL (15 min)

**¿Qué harás?**
- [ ] Ejecutar SQL functions
- [ ] Ejecutar UPDATE masivo
- [ ] Monitorear performance
- [ ] Hacer backups

**Consideraciones:**
- Migration usa transacciones (safe)
- UPDATE masivo es bulk pero con validaciones
- Índices se crean automáticamente
- Rollback disponible con Alembic downgrade

---

### 🧪 **QA / Tester**
**Tiempo de lectura:** 40 minutos
**Prioridad:** MEDIA (después de implementación)

📄 **Documentos a leer:**
1. `RESUMEN_EJECUTIVO.md` → Sección "MÉTRICAS DE ÉXITO" (5 min)
2. `ANALISIS_COLUMNAS_RELACIONADAS.md` → Ejemplos reales (20 min)
3. `COMANDOS_LISTOS_EJECUTAR.md` → Sección CHECKLIST (15 min)

**¿Qué validarás?**
- [ ] 8 columnas nuevas creadas
- [ ] 80-90% de medicamentos con dosis
- [ ] UI muestra campos separados
- [ ] Búsqueda funciona
- [ ] No hay errores

**Test cases:**
```
1. Buscar "paracetamol" → ver nombre sin dosis
2. Verificar card muestra dosis en badge
3. Verificar forma y vía aparecen como badges
4. Verificar medicamentos inyectables muestran volumen
5. Verificar medicamentos sin vía se infieren correctamente
```

---

## 📂 ESTRUCTURA DE DOCUMENTOS

```
memory/
│
├─ 📋 RESUMEN_EJECUTIVO.md
│  └─ Visión general, timeline, checklist
│
├─ 📚 ANALISIS_ESTRUCTURA_MEDICAMENTOS.md
│  └─ Análisis inicial del problema
│  └─ Propuesta de solución
│  └─ Funciones SQL ejemplos
│
├─ 🔍 ANALISIS_COLUMNA_PRODUCTO.md
│  └─ Análisis detallado columna "producto"
│  └─ Problemas encontrados
│  └─ Patrones de transformación
│
├─ 🔗 ANALISIS_COLUMNAS_RELACIONADAS.md
│  └─ Relaciones entre TODAS las columnas
│  └─ 5 ejemplos reales
│  └─ Mapeo correcto de información
│  └─ Estructura mejorada propuesta
│
├─ 🎯 PROMPTS_IMPLEMENTACION.md
│  ├─ PROMPT 1: Crear migrations
│  ├─ PROMPT 2: Crear SQL functions y UPDATE
│  ├─ PROMPT 3: Actualizar modelos Python
│  ├─ PROMPT 4: Actualizar GraphQL
│  └─ PROMPT 5: Componente Frontend mejorado
│
├─ 🚀 COMANDOS_LISTOS_EJECUTAR.md
│  ├─ PASO 1: Crear migration
│  ├─ PASO 2: SQL functions y UPDATE
│  ├─ PASO 3: Modelo Python
│  ├─ PASO 4: GraphQL
│  ├─ PASO 5: Frontend component
│  └─ Checklist de ejecución
│
└─ 📚 INDICE_DOCUMENTACION.md (este archivo)
   └─ Guía de lectura por rol
   └─ Referencias cruzadas
   └─ Preguntas frecuentes
```

---

## 🔗 REFERENCIAS CRUZADAS

### "¿De dónde sale el campo X?"

**nombre_comercial:**
- Originalmente en: `medicamentos_cum.producto`
- Cómo extraerlo: `ANALISIS_COLUMNAS_RELACIONADAS.md` → Función 1
- Código SQL: `COMANDOS_LISTOS_EJECUTAR.md` → PASO 2 → extract_nombre_comercial()

**dosis_cantidad:**
- Originalmente en: `medicamentos_cum.cantidad` (NO en concentracion)
- Cómo extraerlo: `ANALISIS_COLUMNAS_RELACIONADAS.md` → "MAPEO CORRECTO"
- Código SQL: `COMANDOS_LISTOS_EJECUTAR.md` → PASO 2 → extract_dosis_cantidad()

**via_administracion:**
- Originalmente en: `medicamentos_cum.viaadministracion`
- Problema: Tiene "SIN DATO", hay que inferir
- Cómo arreglarlo: `ANALISIS_COLUMNAS_RELACIONADAS.md` → "VÍA DE ADMINISTRACIÓN"
- Código SQL: `COMANDOS_LISTOS_EJECUTAR.md` → PASO 2 → normalize_via_administracion()

**presentacion:**
- Originalmente en: `medicamentos_cum.descripcioncomercial` (PARSEADO)
- Cómo extraerlo: `PROMPTS_IMPLEMENTACION.md` → PROMPT 2 → Función 4
- Código SQL: `COMANDOS_LISTOS_EJECUTAR.md` → PASO 2 → extract_presentacion()

---

### "¿Cómo se ve después de normalizarse?"

**Ejemplo DICLOFENACO:**
- SQL de origen: `ANALISIS_COLUMNAS_RELACIONADAS.md` → "MAPEO..."
- Resultado esperado: `COMANDOS_LISTOS_EJECUTAR.md` → "EJEMPLO DE TRANSFORMACIÓN"
- En UI: `COMANDOS_LISTOS_EJECUTAR.md` → PASO 5

**Ejemplo DORMICUM:**
- Datos con símbolo ®: `ANALISIS_COLUMNAS_RELACIONADAS.md` → "EJEMPLO 2"
- Cómo normalizar: `PROMPTS_IMPLEMENTACION.md` → PROMPT 2, Función 7
- Result en frontend: `ANALISIS_COLUMNAS_RELACIONADAS.md` → "FRONTEND"

---

### "¿Qué campos son TRUE/FALSE?"

**Campos que siempre tienen valor:**
- nombre_comercial (si hay nombre en producto)
- dosis_unidad (casi siempre "mg")
- forma_farmaceutica (ya existe, en tabla medicamentos_cum)

**Campos que pueden ser NULL:**
- marca_comercial (solo si tiene ®)
- dosis_cantidad (si no se puede extraer)
- via_administracion (si es "SIN DATO" y no se puede inferir)
- presentacion (si no está en descripcioncomercial)
- tipo_liberacion (si no es retardada/sostenida/liofilizado)
- volumen_solucion (solo inyectables)

Ver: `ANALISIS_COLUMNAS_RELACIONADAS.md` → "ESTRUCTURA MEJORADA"

---

## ❓ PREGUNTAS FRECUENTES

### P: "¿Se pierden datos al ejecutar la migration?"
**R:** No. Solo se AGREGAN 8 columnas nuevas. Las 10 existentes se mantienen igual. Ver: `PROMPTS_IMPLEMENTACION.md` → PROMPT 1

### P: "¿Tengo que ejecutar SQL directamente o Alembic?"
**R:** Ambos. Migration (Alembic) → crear columnas e índices. Luego SQL → poblar datos. Ver: `COMANDOS_LISTOS_EJECUTAR.md` → PASO 1 y 2

### P: "¿Cuánto tiempo toma el UPDATE masivo?"
**R:** Para 100 medicamentos: < 1 segundo. Para 10,000: ~ 5 segundos. Depende del servidor. Ver: `PROMPTS_IMPLEMENTACION.md` → PROMPT 2, sección UPDATE

### P: "¿Qué pasa si un medicamento no tiene dosis?"
**R:** El campo `dosis_cantidad` queda NULL. `nombre_comercial` y `forma_farmaceutica` igual se rellenan. Ver: `ANALISIS_COLUMNAS_RELACIONADAS.md` → EJEMPLO 5

### P: "¿Se puede revertir?"
**R:** SÍ. Con `alembic downgrade -1` o ejecutar la función downgrade. Ver: `PROMPTS_IMPLEMENTACION.md` → PROMPT 1, sección downgrade()

### P: "¿Qué orden debo seguir?"
**R:** Backend → Frontend. Específicamente: Migration → SQL functions → Modelos → GraphQL → Frontend. Ver: `RESUMEN_EJECUTIVO.md` → PLAN DE IMPLEMENTACIÓN

### P: "¿Afecta a usuarios actuales?"
**R:** No. Los cambios son:
1. Se agregan columnas (no afecta datos existentes)
2. nombre_limpio se mejora (pero sigue existiendo)
3. GraphQL nuevo schema es compatible (campos opcionales)
Ver: `PROMPTS_IMPLEMENTACION.md` → "Backward compatibility"

### P: "¿Cuál columna es la clave para búsquedas?"
**R:** Los índices están en:
- `nombre_comercial` (búsqueda por nombre)
- `via_administracion` (filtro por vía)
- `dosis_cantidad + dosis_unidad` (búsqueda por dosis)
Ver: `COMANDOS_LISTOS_EJECUTAR.md` → PASO 1, sección "Crear índices"

### P: "¿Los tests actuales siguen funcionando?"
**R:** SÍ, si están hechos sobre nombre_limpio. Si quieres testear campos nuevos, agregar tests. Ver: `RESUMEN_EJECUTIVO.md` → CHECKLIST POST-IMPLEMENTACIÓN

### P: "¿Debo cambiar la API/GraphQL?"
**R:** Sí, pero los cambios son aditivos. Se agregan campos sin remover existentes. Ver: `COMANDOS_LISTOS_EJECUTAR.md` → PASO 4

---

## 🎓 FLOW DE APRENDIZAJE RECOMENDADO

### Si estás "perdido":
```
1. Lee RESUMEN_EJECUTIVO.md (10 min)
   ↓
2. Lee tu sección en INDICE_DOCUMENTACION.md (este archivo) (5 min)
   ↓
3. Lee el primer análisis: ANALISIS_COLUMNAS_RELACIONADAS.md (15 min)
   ↓
4. Empieza a implementar con COMANDOS_LISTOS_EJECUTAR.md
```

### Si necesitas entender un error:
```
1. Busca el error en ANALISIS_COLUMNAS_RELACIONADAS.md
   ↓
2. Si no lo encuentras, busca la función relevante en COMANDOS_LISTOS_EJECUTAR.md
   ↓
3. Lee el PROMPT associado en PROMPTS_IMPLEMENTACION.md
```

### Si necesitas una funcionalidad específica:
```
1. Busca en COMANDOS_LISTOS_EJECUTAR.md por palabra clave
   ↓
2. Si no lo encuentras, busca en PROMPTS_IMPLEMENTACION.md
   ↓
3. Si aún no, revisa ANALISIS_COLUMNAS_RELACIONADAS.md
```

---

## 📞 MAP DE RESPONSABILIDADES

| Componente | Quién | Tiempo |
|-----------|-------|--------|
| Migration Alembic | Backend | 20 min |
| SQL Functions | Backend o DBA | 45 min |
| UPDATE masivo | Backend o DBA | 30 min |
| Validación SQL | Backend o QA | 20 min |
| Modelos Python | Backend | 30 min |
| GraphQL Types | Backend | 30 min |
| GraphQL Mappers | Backend | 20 min |
| Componente Frontend | Frontend | 90 min |
| Testing Frontend | Frontend o QA | 30 min |
| **TOTAL** | **2 personas** | **~6 horas** |

---

## ✅ ANTES DE EMPEZAR

**Checklist de requisitos:**
- [ ] Docker con PostgreSQL levantado
- [ ] Backend Python environment activado
- [ ] Frontend Node.js instalado
- [ ] Rama git nueva creada
- [ ] Acceso a BD (usuario/password)
- [ ] Acceso a repositorio (permisos de push)

---

## 🎯 PRÓXIMAS ACCIONES

**Hoy:**
1. Leer este índice
2. Manager → Leer RESUMEN_EJECUTIVO
3. Backend → Leer PROMPTS 1 y 2
4. Frontend → Leer análisis

**Mañana:**
1. Backend → Ejecutar PASO 1 y 2
2. Backend → Ejecutar PASO 3 y 4

**Pasado:**
1. Frontend → Ejecutar PASO 5
2. Frontend → Testing

**Viernes:**
1. Todos → Validación final
2. Manager → Checklist
3. PR → Review y merge

---

## 📚 OTROS RECURSOS

**Si necesitas entender Alembic:**
- Oficial: https://alembic.sqlalchemy.org/
- Quick start en COMANDOS_LISTOS_EJECUTAR.md PASO 1

**Si necesitas entender funciones SQL:**
- Revisión de PostgreSQL docs para regexp_matches()
- Ejemplos en COMANDOS_LISTOS_EJECUTAR.md PASO 2

**Si necesitas entender GraphQL:**
- Strawberry docs: https://strawberry.rocks/
- Ejemplos en COMANDOS_LISTOS_EJECUTAR.md PASO 4

**Si necesitas entender el proyecto:**
- Ver: backend/app/models/medicamento.py (modelo actual)
- Ver: frontend/src/components/BuscadorMedicamentos.tsx (componente actual)

---

**Documento generado:** 16 de Marzo 2026
**Versión:** 1.0
**Status:** ✅ Listo para distribución
