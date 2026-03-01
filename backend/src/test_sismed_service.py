"""
Pruebas unitarias para el servicio SISMED y el modelo PrecioMedicamento.

Ejecutar:
    python -m pytest backend/src/test_sismed_service.py -v
"""

from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.dialects import postgresql

from app.models.medicamento import PrecioMedicamento
from app.services.sismed_socrata_service import (
    _fetch_latest_fechacorte,
    _map_record,
    _normalize_canal,
    _normalize_regimen,
    _parse_decimal,
    _parse_int,
    _resolve_field,
    construir_upsert_precios,
)


# ===========================================================================
# Modelo PrecioMedicamento – pruebas estructurales
# ===========================================================================


class PrecioMedicamentoModelTests(unittest.TestCase):
    """Verifica que el modelo se haya definido correctamente."""

    def test_tablename(self):
        self.assertEqual(PrecioMedicamento.__tablename__, "precios_medicamentos")

    def test_primary_key_is_id(self):
        pk_cols = [col.name for col in PrecioMedicamento.__table__.primary_key.columns]
        self.assertEqual(pk_cols, ["id"])

    def test_required_columns_exist(self):
        cols = {col.name for col in PrecioMedicamento.__table__.columns}
        required = {
            "id",
            "id_cum",
            "canal_mercado",
            "regimen_precios",
            "precio_regulado_maximo",
            "acto_administrativo_precio",
            "precio_sismed_minimo",
            "precio_sismed_maximo",
            "ultima_actualizacion",
        }
        for field in required:
            self.assertIn(field, cols, f"Columna '{field}' no encontrada en precios_medicamentos")

    def test_id_cum_is_not_nullable(self):
        # id_cum sigue siendo NOT NULL aunque no tenga FK a nivel BD
        id_cum_col = PrecioMedicamento.__table__.columns["id_cum"]
        self.assertFalse(id_cum_col.nullable)

    def test_id_cum_has_no_db_foreign_key(self):
        # La FK fue eliminada para permitir precios SISMED de CUMs históricos
        # que no están en el catálogo activo de medicamentos_cum.
        id_cum_col = PrecioMedicamento.__table__.columns["id_cum"]
        self.assertEqual(len(id_cum_col.foreign_keys), 0)

    def test_unique_constraint_exists(self):
        constraint_names = {
            c.name
            for c in PrecioMedicamento.__table__.constraints
        }
        self.assertIn("uq_precio_cum_canal", constraint_names)

    def test_unique_constraint_columns(self):
        target = next(
            c for c in PrecioMedicamento.__table__.constraints
            if c.name == "uq_precio_cum_canal"
        )
        col_names = [col.name for col in target.columns]
        self.assertEqual(sorted(col_names), sorted(["id_cum", "canal_mercado"]))

    def test_canal_mercado_max_length(self):
        canal_col = PrecioMedicamento.__table__.columns["canal_mercado"]
        self.assertEqual(canal_col.type.length, 3)

    def test_numeric_scale(self):
        for col_name in ("precio_regulado_maximo", "precio_sismed_minimo", "precio_sismed_maximo"):
            col = PrecioMedicamento.__table__.columns[col_name]
            self.assertEqual(col.type.precision, 14)
            self.assertEqual(col.type.scale, 4)


# ===========================================================================
# Helpers de conversión
# ===========================================================================


class ParseIntTests(unittest.TestCase):
    def test_valid_string(self):
        self.assertEqual(_parse_int("123456"), 123456)

    def test_valid_int(self):
        self.assertEqual(_parse_int(42), 42)

    def test_none_returns_none(self):
        self.assertIsNone(_parse_int(None))

    def test_invalid_string(self):
        self.assertIsNone(_parse_int("abc"))

    def test_float_string(self):
        self.assertEqual(_parse_int("7.0"), 7)


class ParseDecimalTests(unittest.TestCase):
    def test_plain_number(self):
        self.assertEqual(_parse_decimal("52300.50"), Decimal("52300.50"))

    def test_thousands_dot_decimal_comma(self):
        # "1.234,56" → Decimal("1234.56")
        self.assertEqual(_parse_decimal("1.234,56"), Decimal("1234.56"))

    def test_thousands_comma_decimal_dot(self):
        # "1,234.56" → Decimal("1234.56")
        self.assertEqual(_parse_decimal("1,234.56"), Decimal("1234.56"))

    def test_comma_only(self):
        self.assertEqual(_parse_decimal("52300,50"), Decimal("52300.50"))

    def test_none_returns_none(self):
        self.assertIsNone(_parse_decimal(None))

    def test_empty_string(self):
        self.assertIsNone(_parse_decimal(""))

    def test_dash_returns_none(self):
        self.assertIsNone(_parse_decimal("-"))

    def test_integer_value(self):
        self.assertEqual(_parse_decimal(100), Decimal("100"))


class NormalizeCanalTests(unittest.TestCase):
    def test_ins_uppercase(self):
        self.assertEqual(_normalize_canal("INS"), "INS")

    def test_com_lowercase(self):
        self.assertEqual(_normalize_canal("com"), "COM")

    def test_institucional_alias(self):
        self.assertEqual(_normalize_canal("Institucional"), "INS")

    def test_comercial_alias(self):
        self.assertEqual(_normalize_canal("COMERCIAL"), "COM")

    def test_i_alias(self):
        self.assertEqual(_normalize_canal("I"), "INS")

    def test_c_alias(self):
        self.assertEqual(_normalize_canal("C"), "COM")

    def test_invalid(self):
        self.assertIsNone(_normalize_canal("OTRO"))

    def test_none(self):
        self.assertIsNone(_normalize_canal(None))

    # Valores reales del campo transaccionsismeddesc del dataset 3he6-m866
    def test_transaccion_primaria_institucional(self):
        self.assertEqual(
            _normalize_canal("TRANSACCION PRIMARIA INSTITUCIONAL"), "INS"
        )

    def test_transaccion_primaria_comercial(self):
        self.assertEqual(
            _normalize_canal("TRANSACCION PRIMARIA COMERCIAL"), "COM"
        )

    def test_transaccion_secundaria_institucional(self):
        self.assertEqual(
            _normalize_canal("TRANSACCION SECUNDARIA INSTITUCIONAL"), "INS"
        )

    def test_transaccion_secundaria_comercial(self):
        self.assertEqual(
            _normalize_canal("TRANSACCION SECUNDARIA COMERCIAL"), "COM"
        )


class NormalizeRegimenTests(unittest.TestCase):
    def test_valid_1(self):
        self.assertEqual(_normalize_regimen("1"), 1)

    def test_valid_2(self):
        self.assertEqual(_normalize_regimen(2), 2)

    def test_valid_3(self):
        self.assertEqual(_normalize_regimen("3"), 3)

    def test_zero_invalid(self):
        self.assertIsNone(_normalize_regimen(0))

    def test_four_invalid(self):
        self.assertIsNone(_normalize_regimen(4))

    def test_none(self):
        self.assertIsNone(_normalize_regimen(None))

    def test_string_invalid(self):
        self.assertIsNone(_normalize_regimen("libertad"))


# ===========================================================================
# Mapeo de registros crudos
# ===========================================================================


class MapRecordTests(unittest.TestCase):
    """Prueba _map_record con nombres de columna canónicos y alternativos."""

    def _base_raw(self) -> dict:
        return {
            "expediente": "123456",
            "consecutivocum": "1",
            "canal": "INS",
            "regimen": "1",
            "acto_administrativo": "Circular 013 de 2022",
            "precio_maximo_venta_regulado": "52300.50",
            "precio_minimo_venta": "45000",
            "precio_maximo_venta": "55000",
        }

    def test_id_cum_construction(self):
        result = _map_record(self._base_raw())
        self.assertEqual(result["id_cum"], "123456-01")

    def test_id_cum_zero_padding(self):
        raw = self._base_raw()
        raw["consecutivocum"] = "2"
        result = _map_record(raw)
        self.assertEqual(result["id_cum"], "123456-02")

    def test_canal_mercado_mapped(self):
        result = _map_record(self._base_raw())
        self.assertEqual(result["canal_mercado"], "INS")

    def test_regimen_mapped(self):
        result = _map_record(self._base_raw())
        self.assertEqual(result["regimen_precios"], 1)

    def test_acto_administrativo_mapped(self):
        result = _map_record(self._base_raw())
        self.assertEqual(result["acto_administrativo_precio"], "Circular 013 de 2022")

    def test_precios_mapped(self):
        result = _map_record(self._base_raw())
        self.assertEqual(result["precio_regulado_maximo"], Decimal("52300.50"))
        self.assertEqual(result["precio_sismed_minimo"], Decimal("45000"))
        self.assertEqual(result["precio_sismed_maximo"], Decimal("55000"))

    def test_missing_expediente_returns_empty(self):
        raw = self._base_raw()
        del raw["expediente"]
        self.assertEqual(_map_record(raw), {})

    def test_missing_consecutivo_returns_empty(self):
        raw = self._base_raw()
        del raw["consecutivocum"]
        self.assertEqual(_map_record(raw), {})

    def test_invalid_canal_returns_empty(self):
        raw = self._base_raw()
        raw["canal"] = "OTRO"
        self.assertEqual(_map_record(raw), {})

    def test_alternative_column_names(self):
        """Verifica que el resolvedor de columnas alternativas funcione."""
        raw = {
            "expediente": "999",
            "consecutivo": "3",     # alternativa a consecutivocum
            "canal_mercado": "COM",  # alternativa a transaccionsismeddesc
            "regimen_precios": "2",
            "precio_maximo_regulado": "38000",
            "precio_minimo": "31000",
            "precio_maximo": "40000",
        }
        result = _map_record(raw)
        self.assertEqual(result["id_cum"], "999-03")
        self.assertEqual(result["canal_mercado"], "COM")
        self.assertEqual(result["regimen_precios"], 2)

    def test_real_socrata_column_names(self):
        """Verifica el mapeo con los nombres reales del dataset 3he6-m866."""
        raw = {
            "expedientecum": "20097257",
            "consecutivo": "18",
            "transaccionsismeddesc": "TRANSACCION PRIMARIA INSTITUCIONAL",
            "valorminimo": "0.00000",
            "valormaximo": "52300.50",
        }
        result = _map_record(raw)
        self.assertEqual(result["id_cum"], "20097257-18")
        self.assertEqual(result["canal_mercado"], "INS")
        self.assertEqual(result["precio_sismed_maximo"], Decimal("52300.50"))

    def test_record_has_ultima_actualizacion(self):
        result = _map_record(self._base_raw())
        self.assertIn("ultima_actualizacion", result)
        self.assertIsNotNone(result["ultima_actualizacion"])


# ===========================================================================
# Resolución de campos con candidatos alternativos
# ===========================================================================


class ResolveFieldTests(unittest.TestCase):
    def test_first_candidate_wins(self):
        # "consecutivo" es el primer candidato real del dataset (3he6-m866);
        # si coexiste con "consecutivocum", debe ganar "consecutivo".
        raw = {"expediente": "100", "consecutivo": "1", "consecutivocum": "2"}
        self.assertEqual(_resolve_field(raw, "consecutivocum"), "1")

    def test_fallback_candidate(self):
        # Sin "consecutivo", cae al fallback "consecutivocum"
        raw = {"expediente": "100", "consecutivocum": "5"}
        self.assertEqual(_resolve_field(raw, "consecutivocum"), "5")

    def test_returns_none_when_no_candidate(self):
        raw = {"expediente": "100"}
        self.assertIsNone(_resolve_field(raw, "consecutivocum"))


# ===========================================================================
# Construcción del UPSERT
# ===========================================================================


class ConstruirUpsertPreciosTests(unittest.TestCase):
    def _sample_rows(self) -> list[dict]:
        from uuid import uuid4

        return [
            {
                "id": uuid4(),
                "id_cum": "123456-01",
                "canal_mercado": "INS",
                "regimen_precios": 1,
                "precio_regulado_maximo": Decimal("52300.50"),
                "acto_administrativo_precio": "Circular 013 de 2022",
                "precio_sismed_minimo": Decimal("45000"),
                "precio_sismed_maximo": Decimal("55000"),
                "ultima_actualizacion": None,
            }
        ]

    def test_returns_insert_statement(self):
        from sqlalchemy.dialects.postgresql import Insert

        stmt = construir_upsert_precios(self._sample_rows())
        self.assertIsInstance(stmt, Insert)

    def test_compiled_contains_on_conflict(self):
        stmt = construir_upsert_precios(self._sample_rows())
        compiled = stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": False},
        )
        sql_text = str(compiled).upper()
        self.assertIn("ON CONFLICT", sql_text)
        self.assertIn("DO UPDATE", sql_text)

    def test_compiled_targets_correct_table(self):
        stmt = construir_upsert_precios(self._sample_rows())
        compiled = str(stmt.compile(dialect=postgresql.dialect()))
        self.assertIn("precios_medicamentos", compiled)

    def test_upsert_excludes_id_and_id_cum_from_update(self):
        """id y id_cum NO deben aparecer en el SET del ON CONFLICT."""
        stmt = construir_upsert_precios(self._sample_rows())
        compiled = str(stmt.compile(dialect=postgresql.dialect()))
        # La cláusula SET debe actualizar campos de precio, no la PK
        self.assertIn("precio_sismed_minimo", compiled)
        self.assertIn("ultima_actualizacion", compiled)


# ===========================================================================
# _fetch_latest_fechacorte
# ===========================================================================


class FetchLatestFechacorteTests(unittest.IsolatedAsyncioTestCase):
    """Pruebas para la función que obtiene la fechacorte más reciente."""

    def _make_mock_response(self, payload: list[dict]) -> AsyncMock:
        mock_resp = AsyncMock()
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = AsyncMock(return_value=payload)
        return mock_resp

    async def test_returns_max_fecha_from_valid_response(self):
        """Extrae max_fecha del primer elemento de la respuesta JSON."""
        resp = self._make_mock_response([{"max_fecha": "2024/10/01"}])
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=resp)
        result = await _fetch_latest_fechacorte(mock_session)
        self.assertEqual(result, "2024/10/01")

    async def test_returns_none_on_empty_list(self):
        """Lista vacía → retorna None."""
        resp = self._make_mock_response([])
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=resp)
        result = await _fetch_latest_fechacorte(mock_session)
        self.assertIsNone(result)

    async def test_returns_none_when_key_missing(self):
        """Respuesta sin clave max_fecha → retorna None."""
        resp = self._make_mock_response([{"other_key": "value"}])
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=resp)
        result = await _fetch_latest_fechacorte(mock_session)
        self.assertIsNone(result)

    async def test_returns_none_on_http_error(self):
        """Error de red → retorna None sin propagar la excepción."""
        import aiohttp as _aiohttp

        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=_aiohttp.ClientConnectionError("fail"))
        result = await _fetch_latest_fechacorte(mock_session)
        self.assertIsNone(result)

    async def test_sends_select_max_fechacorte_param(self):
        """Verifica que la llamada incluye $select=max(fechacorte) as max_fecha."""
        resp = self._make_mock_response([{"max_fecha": "2025/01/01"}])
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=resp)
        await _fetch_latest_fechacorte(mock_session)
        call_kwargs = mock_session.get.call_args
        params = call_kwargs[1]["params"] if call_kwargs[1].get("params") else call_kwargs[0][1]
        self.assertIn("$select", params)
        self.assertIn("max(fechacorte)", params["$select"])


# ===========================================================================
# Servicio asíncrono (integración con mock HTTP)
# ===========================================================================


class SincronizarPreciosSismedTests(unittest.IsolatedAsyncioTestCase):
    """Prueba la función principal con un servidor HTTP simulado."""

    def _make_batch(self, size: int = 3) -> list[dict]:
        return [
            {
                "expediente": str(100 + i),
                "consecutivocum": "1",
                "canal": "INS",
                "regimen": "1",
                "acto_administrativo": "Circular 001 de 2025",
                "precio_maximo_venta_regulado": "50000",
                "precio_minimo_venta": "40000",
                "precio_maximo_venta": "52000",
            }
            for i in range(size)
        ]

    async def test_sincronizar_returns_ok_on_success(self):
        from app.services.sismed_socrata_service import sincronizar_precios_sismed

        # Primera página con 3 filas; segunda página vacía → paginación termina
        first_page = self._make_batch(3)
        empty_page: list = []

        mock_response_first = AsyncMock()
        mock_response_first.__aenter__ = AsyncMock(return_value=mock_response_first)
        mock_response_first.__aexit__ = AsyncMock(return_value=False)
        mock_response_first.raise_for_status = MagicMock()
        mock_response_first.json = AsyncMock(return_value=first_page)

        mock_response_empty = AsyncMock()
        mock_response_empty.__aenter__ = AsyncMock(return_value=mock_response_empty)
        mock_response_empty.__aexit__ = AsyncMock(return_value=False)
        mock_response_empty.raise_for_status = MagicMock()
        mock_response_empty.json = AsyncMock(return_value=empty_page)

        mock_get = MagicMock(side_effect=[mock_response_first, mock_response_empty])
        mock_http_session = MagicMock()
        mock_http_session.get = mock_get
        mock_http_session.__aenter__ = AsyncMock(return_value=mock_http_session)
        mock_http_session.__aexit__ = AsyncMock(return_value=False)

        mock_db_session = AsyncMock()
        mock_db_session.__aenter__ = AsyncMock(return_value=mock_db_session)
        mock_db_session.__aexit__ = AsyncMock(return_value=False)
        mock_db_session.execute = AsyncMock()
        mock_db_session.commit = AsyncMock()

        mock_sf = MagicMock(return_value=mock_db_session)

        with patch(
            "app.services.sismed_socrata_service.aiohttp.ClientSession",
            return_value=mock_http_session,
        ), patch(
            "app.services.sismed_socrata_service._fetch_latest_fechacorte",
            new=AsyncMock(return_value=None),
        ):
            result = await sincronizar_precios_sismed(mock_sf)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["registros"], 3)

    async def test_sincronizar_returns_error_on_http_failure(self):
        import aiohttp as _aiohttp

        from app.services.sismed_socrata_service import sincronizar_precios_sismed

        mock_get = MagicMock(side_effect=_aiohttp.ClientConnectionError("Connection refused"))
        mock_http_session = MagicMock()
        mock_http_session.get = mock_get
        mock_http_session.__aenter__ = AsyncMock(return_value=mock_http_session)
        mock_http_session.__aexit__ = AsyncMock(return_value=False)

        mock_sf = MagicMock()

        with patch(
            "app.services.sismed_socrata_service.aiohttp.ClientSession",
            return_value=mock_http_session,
        ), patch(
            "app.services.sismed_socrata_service._fetch_latest_fechacorte",
            new=AsyncMock(return_value=None),
        ):
            result = await sincronizar_precios_sismed(mock_sf)

        self.assertEqual(result["status"], "error")
        self.assertIn("error", result)

    async def test_registros_invalidos_son_descartados(self):
        """Filas sin canal válido deben descartarse sin lanzar excepción."""
        from app.services.sismed_socrata_service import sincronizar_precios_sismed

        # Todas las filas tienen canal inválido
        bad_batch = [
            {
                "expediente": "200",
                "consecutivocum": "1",
                "canal": "INVALIDO",
                "regimen": "1",
            }
        ]
        empty_page: list = []

        mock_response_bad = AsyncMock()
        mock_response_bad.__aenter__ = AsyncMock(return_value=mock_response_bad)
        mock_response_bad.__aexit__ = AsyncMock(return_value=False)
        mock_response_bad.raise_for_status = MagicMock()
        mock_response_bad.json = AsyncMock(return_value=bad_batch)

        mock_response_empty = AsyncMock()
        mock_response_empty.__aenter__ = AsyncMock(return_value=mock_response_empty)
        mock_response_empty.__aexit__ = AsyncMock(return_value=False)
        mock_response_empty.raise_for_status = MagicMock()
        mock_response_empty.json = AsyncMock(return_value=empty_page)

        mock_get = MagicMock(side_effect=[mock_response_bad, mock_response_empty])
        mock_http_session = MagicMock()
        mock_http_session.get = mock_get
        mock_http_session.__aenter__ = AsyncMock(return_value=mock_http_session)
        mock_http_session.__aexit__ = AsyncMock(return_value=False)

        mock_sf = MagicMock()

        with patch(
            "app.services.sismed_socrata_service.aiohttp.ClientSession",
            return_value=mock_http_session,
        ), patch(
            "app.services.sismed_socrata_service._fetch_latest_fechacorte",
            new=AsyncMock(return_value=None),
        ):
            result = await sincronizar_precios_sismed(mock_sf)

        # No se ejecutó ningún upsert → 0 registros procesados
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["registros"], 0)


if __name__ == "__main__":
    unittest.main()
