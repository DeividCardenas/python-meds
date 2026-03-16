# PROMPT 3: FRONTEND AGENT
## REACT COMPONENT & GRAPHQL QUERY UPDATE

You are a Frontend Agent. Your task is to update React components and GraphQL queries to display new medicamento fields.

### PREREQUISITE
✅ Backend-Code Agent must have completed STEP 1-5 (models + GraphQL schema updated)

### OBJECTIVE
Update BuscadorMedicamentos component to show new fields: nombre_comercial, dosis, via_administracion, presentacion, tipo_liberacion

---

## TASK 1: UPDATE GRAPHQL QUERY

**File**: `frontend/src/components/BuscadorMedicamentos.tsx`

**Action**: Find the `SearchMedicamentosDocument` GraphQL query and replace/update it to include new fields:

```graphql
// Find and replace this section in the file:
const SearchMedicamentosDocument = gql`
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
      nombreComercial
      marcaComercial
      nombreLimpio
      dosisCanitidad
      dosisUnidad
      formaFarmaceutica
      tipoFormaDetalles
      viaAdministracion
      presentacion
      tipoLiberacion
      volumenSolucion
      principioActivo
      laboratorio
      registroInvima
      estadoCum
      activo
      esRegulado
      precioUnitario
      precioMaximoRegulado
    }
  }
`;
```

**Verify**: Query syntax valid (no GraphQL errors when app loads).

---

## TASK 2: UPDATE COMPONENT CARD JSX

**File**: `frontend/src/components/BuscadorMedicamentos.tsx`

**Action**: Find the card rendering section (around line 302-350, inside the `{resultados.map((item) => {` loop) and replace the entire `<article>` element with this:

```jsx
{/**START REPLACE: Find the <article> tag inside resultados.map and replace until closing </article> **/}

<article
  key={item.id}
  className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition duration-200 hover:scale-105 hover:shadow-lg"
>
  {/* Header: Nombre + Dosis */}
  <div className="flex items-baseline justify-between gap-3 mb-3">
    <div className="flex-1">
      <h3 className="text-lg font-bold text-slate-900">
        {toTitleCase(item.nombreComercial || item.nombreLimpio || "Nombre no disponible")}
      </h3>
      {item.dosisCanitidad && (
        <p className="text-sm text-slate-500 mt-1">
          {item.dosisCanitidad} {item.dosisUnidad}
        </p>
      )}
    </div>

    {/* Badge Regulado */}
    {item.esRegulado ? (
      <span className="inline-flex rounded-full bg-orange-100 px-2.5 py-0.5 text-xs font-semibold text-orange-700 whitespace-nowrap">
        🔒 Regulado{item.precioMaximoRegulado ? ` · Máx ${formatPrice(item.precioMaximoRegulado)}` : ""}
      </span>
    ) : null}
  </div>

  {/* Badges: Forma + Vía + Liberación */}
  <div className="flex flex-wrap gap-2 mb-3">
    {item.formaFarmaceutica && (
      <span className="inline-flex rounded-full bg-blue-100 px-2.5 py-1 text-xs font-medium text-blue-700">
        {toTitleCase(item.formaFarmaceutica)}
      </span>
    )}

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

  {/* Estado CUM Badge */}
  {item.estadoCum ? (
    <span
      className={`mb-2 mr-2 inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${
        item.activo
          ? "bg-emerald-100 text-emerald-700"
          : "bg-red-100 text-red-700"
      }`}
    >
      {item.activo ? "✓" : "✗"} {item.estadoCum}
    </span>
  ) : null}

  {/* Principio Activo */}
  {item.principioActivo && (
    <p className="text-sm text-slate-600 mb-2">
      <span className="font-medium">{toTitleCase(item.principioActivo)}</span>
    </p>
  )}

  {/* Laboratorio */}
  {item.laboratorio && (
    <p className="mt-2 flex items-center gap-2 text-sm text-slate-600">
      <svg viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current stroke-2" aria-hidden="true">
        <path d="M3 21h18" />
        <path d="M5 21V9l7-4 7 4v12" />
        <path d="M9 21v-4h6v4" />
      </svg>
      {item.laboratorio}
    </p>
  )}

  {/* Presentación */}
  {item.presentacion && (
    <p className="text-xs text-slate-500 mt-2">
      Presentación: <span className="font-medium">{item.presentacion}</span>
    </p>
  )}

  {/* Precio */}
  {item.precioUnitario && (
    <div className="mt-3 flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
      <span className="text-xs text-slate-500">Precio unitario</span>
      <span className="font-semibold text-slate-900">
        {formatPrice(item.precioUnitario)}
      </span>
    </div>
  )}

  {/* Botón Comparativa */}
  <button
    type="button"
    onClick={() => abrirComparativa(item.principioActivo)}
    disabled={!item.principioActivo}
    className="mt-4 w-full rounded-lg border border-blue-200 px-3 py-1.5 text-xs font-semibold text-blue-700 transition hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"
  >
    Ver comparativa de precios
  </button>
</article>

{/**END REPLACE**/}
```

**Verify**: No JSX syntax errors. Component renders in browser.

---

## TASK 3: TEST IN BROWSER

**Action**: Start frontend development server:

```bash
cd frontend
npm run dev
```

**Action**: Open browser and test:

1. Go to http://localhost:3000
2. Search for a medication (e.g., "paracetamol")
3. Verify card displays:
   - [ ] Medication name (nombre_comercial)
   - [ ] Dose quantity and unit (dosisCanitidad + dosisUnidad)
   - [ ] Badge for forma_farmaceutica (blue badge)
   - [ ] Badge for via_administracion (green badge)
   - [ ] Badge for tipo_liberacion if applicable (purple badge)
   - [ ] Principio activo (gray text)
   - [ ] Laboratorio (with building icon)
   - [ ] Presentación (if available)
   - [ ] Price if available
   - [ ] "Ver comparativa" button

4. Check browser console (F12):
   - [ ] No JavaScript errors (red X)
   - [ ] No GraphQL errors
   - [ ] No network 500 errors

---

## TASK 4: VERIFY DATA FLOW

**Action**: Open browser DevTools (F12) → Network tab

**Action**: Perform search, watch GraphQL request:

1. Look for `operations` or `graphql` request
2. Click it
3. Check "Response" tab shows all new fields:
   - nombreComercial
   - dosisCanitidad
   - dosisUnidad
   - viaAdministracion
   - presentacion
   - tipoLiberacion

Expected: All fields present in response (may be null, but key should exist).

---

## TASK 5: TEST EDGE CASES

**Action**: Search for medications with different characteristics:

- [ ] Medication WITHOUT dosis → Verify dose section not shown (empty)
- [ ] Medication WITHOUT viaAdministracion → Verify green badge not shown
- [ ] Medication WITH tipo_liberacion → Verify purple badge appears
- [ ] Inyectable medication → Verify "solución inyectable" badge appears
- [ ] Regulated medication → Verify orange "🔒 Regulado" badge appears

---

## COMPLETION CHECKLIST

- [ ] GraphQL query updated with 8 new fields
- [ ] Query syntax valid (no GraphQL errors)
- [ ] Card JSX replaced with new version
- [ ] Component renders without errors
- [ ] Browser shows no console errors
- [ ] Cards display: nombre, dosis, forma badge, via badge, liberacion badge
- [ ] Principio activo displays
- [ ] Laboratorio displays
- [ ] Presentacion displays (if available)
- [ ] Precio displays (if available)
- [ ] "Ver comparativa" button works
- [ ] All badges render with correct colors (blue, green, purple, orange)
- [ ] Responsive design works on mobile

## SUCCESS CRITERIA

✅ Component renders all 8 new fields correctly
✅ GraphQL query includes all new fields
✅ Cards display information in clean, organized way
✅ No console errors
✅ No GraphQL errors
✅ Responsive on desktop and mobile
✅ Ready for QA/Testing Agent (next phase)

## IF SOMETHING FAILS

**Component won't render**: Check TypeScript errors (npm run build)
**Fields show as undefined**: GraphQL query missing fields - check query syntax
**Badges not showing**: Check item.field names match GraphQL response (camelCase)
**Styling looks wrong**: Verify TailwindCSS classes are valid (rounded-full, bg-blue-100, etc)
**GraphQL error**: Check Backend-Code Agent completed STEP 1-5
**No data appears**: Verify backend is running (`npm run dev` in separate terminal for backend)

---

**REPORT**: When complete, report success. QA/Testing Agent can now validate entire implementation.
