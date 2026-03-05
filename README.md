# python-meds

Plataforma de catálogo de medicamentos y cotización de precios construida con FastAPI, PostgreSQL (pgvector), Redis y Celery.

---

## Inicio rápido

```bash
# 1. Copiar el template de variables de entorno y completar credenciales
cp .env.example .env

# 2. Crear el directorio de uploads del worker
mkdir -p backend/uploads

# 3. Construir imágenes y levantar todos los servicios
docker compose build --no-cache
docker compose up -d

# 4. Verificar que todos los servicios estén saludables
docker compose ps
```

---

## Poblar el sistema (orden obligatorio)

Cada paso depende del anterior. El sistema queda listo para cotizaciones al finalizar el Paso 4.

```
INVIMA (internet)
      ↓  Paso 1 — sincronización CUM
   medicamentos + medicamentos_cum
      ↓  Paso 2 — sincronización SISMED
   precios_medicamentos
      ↓  Paso 3 — seed regulados CNPMDM
   precios_regulados_cnpmdm
      ↓  Paso 4 — seed proveedores demo
   proveedores + precios_proveedor
      ↓
  ✅ Sistema listo para cotizaciones
```

### Paso 1 — Catálogo CUM de INVIMA

Descarga todos los medicamentos vigentes desde datos.gov.co. **Requiere internet.**
Puede tardar varios minutos.

Ejecutar la mutation en `http://localhost:8000/graphql`:

```graphql
mutation {
  sincronizarCatalogos(incluirSismed: false) {
    cum { tarea mensaje }
  }
}
```

Seguir el progreso en los logs del worker:

```bash
docker compose logs worker --follow
# Esperar: "Sincronización CUM completada: X registros insertados/actualizados"
# Salir con Ctrl+C
```

Verificar:

```bash
docker compose exec db psql -U genhospi_admin -d genhospi_catalog \
  -c "SELECT COUNT(*) AS medicamentos FROM medicamentos;"
```

---

### Paso 2 — Precios SISMED (Ministerio de Salud)

Sincroniza los precios de referencia oficiales desde datos.gov.co.
Requiere que el Paso 1 esté completo (FK a `medicamentos_cum`).

```graphql
mutation {
  sincronizarCatalogos(incluirSismed: true) {
    cum   { tarea mensaje }
    sismed { tarea mensaje }
  }
}
```

```bash
docker exec python-meds-worker-1 celery -A app.worker.tasks.celery_app call task_sincronizar_precios_sismed
#Sincronizar mediante comando
```

Verificar:

```bash
docker compose exec db psql -U genhospi_admin -d genhospi_catalog \
  -c "SELECT COUNT(*) AS precios_sismed FROM precios_medicamentos;"
```

---

### Paso 3 — Precios regulados CNPMDM (demo)

Carga ~40 principios activos con sus precios máximos regulados por el gobierno.

```bash
docker compose exec backend python /app/src/seed_regulados_demo.py
```

Verificar:

```bash
docker compose exec db psql -U genhospi_admin -d genhospi_catalog \
  -c "SELECT COUNT(*) AS regulados FROM precios_regulados_cnpmdm;"
```

---

### Paso 4 — Precios de proveedores demo

Crea 3 proveedores ficticios (Megalabs, La Santé, Disnafar) con precios realistas
en COP para todos los CUM activos. Necesario para que el pipeline de cotización
devuelva resultados.

> Reemplazar `<POSTGRES_PASSWORD>` con el valor de `POSTGRES_PASSWORD` de tu `.env`.

```bash
docker compose exec \
  -e PRICING_DATABASE_URL="postgresql+asyncpg://genhospi_admin:<POSTGRES_PASSWORD>@db:5432/genhospi_pricing" \
  backend python /app/src/seed_precios_proveedor_demo.py
```

Verificar:

```bash
docker compose exec db psql -U genhospi_admin -d genhospi_pricing \
  -c "SELECT nombre FROM proveedores;"

docker compose exec db psql -U genhospi_admin -d genhospi_pricing \
  -c "SELECT COUNT(*) AS precios_proveedor FROM precios_proveedor;"
```

---

### Verificación final

```bash
docker compose exec db psql -U genhospi_admin -d genhospi_catalog \
  -c "SELECT COUNT(*) AS medicamentos       FROM medicamentos;
      SELECT COUNT(*) AS precios_sismed     FROM precios_medicamentos;
      SELECT COUNT(*) AS regulados          FROM precios_regulados_cnpmdm;"

docker compose exec db psql -U genhospi_admin -d genhospi_pricing \
  -c "SELECT COUNT(*) AS precios_proveedor FROM precios_proveedor;"
```

---

## Servicios disponibles

| Servicio        | URL                              |
|-----------------|----------------------------------|
| Backend GraphQL | http://localhost:8000/graphql    |
| Health check    | http://localhost:8000/health     |
| Frontend        | http://localhost:3000            |
| pgAdmin         | http://localhost:5050            |

---

## Conexión a PostgreSQL desde pgAdmin / DBeaver

El contenedor mapea el **puerto 5433 del host → puerto 5432 del contenedor** para evitar conflictos con instalaciones locales de PostgreSQL.

| Campo        | Valor                                               |
|--------------|-----------------------------------------------------|
| **Host**     | `127.0.0.1`                                         |
| **Puerto**   | `5433`                                              |
| **Usuario**  | `genhospi_admin`                                    |
| **Contraseña** | valor de `POSTGRES_PASSWORD` en `.env`            |
| **Base de datos** | `genhospi_catalog` o `genhospi_pricing`        |

> **Importante:** usar siempre el puerto **5433** (host), nunca 5432.

---

## Borrar volúmenes y reconstruir desde cero

Usar si las credenciales cambiaron o se necesita un estado limpio.
> ⚠️ Esto **elimina todos los datos** de las bases de datos.

```bash
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

Luego repetir los pasos de poblado de datos desde el Paso 1.

---

## Arquitectura

| Servicio   | Dirección interna | Puerto host |
|------------|-------------------|-------------|
| PostgreSQL | `db:5432`         | `5433`      |
| Redis      | `redis:6379`      | `127.0.0.1:6379` |
| Backend    | `backend:8000`    | `8000`      |
| Frontend   | `frontend:80`     | `3000`      |
| pgAdmin    | —                 | `5050`      |

Los servicios dentro de la red Docker se comunican por nombre de servicio (ej. `db:5432`).
Las herramientas externas en el host conectan por el puerto mapeado (ej. `localhost:5433`).

---

## Seguridad

- Las credenciales **nunca** deben estar en `docker-compose.yml` ni commitarse. Usar exclusivamente el archivo `.env` (cubierto por `.gitignore`).
- Redis requiere autenticación (`REDIS_PASSWORD`). Las URLs de Celery deben incluir la contraseña: `redis://:PASSWORD@redis:6379/0`.
- CORS configurado vía `CORS_ORIGINS` en `.env`. Para producción, reemplazar `http://localhost:3000` por el dominio real.
- Rate limiting activo: 120 req/min por IP de forma global; 20 req/min en el endpoint de exportación de cotizaciones.
