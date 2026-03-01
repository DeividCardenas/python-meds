"""Bulk Quoting Matching Engine — Genhospi × Sanitas.

Implements the 3-stage deterministic matching pipeline defined in the
Technical Design Document (2026-02-28).  No ML / embedding stage per
executive decision.  Every match decision is fully auditable.

Stage Summary
-------------
    PRE    Hospital-scoped Synonym Dictionary lookup  (exact, O(1))
    S1     Exact SQL match on INN + form; Python concentration hard barrier
    S2     pg_trgm ≥ 0.85 on INN + form group guard; Python hard barrier
    S3     NO_MATCH: structured alert record with closest candidate

The Hard Barrier
----------------
Concentration comparison is NEVER relaxed.  The SQL layers retrieve
candidates; Python re-parses the DB concentracion string through the same
drug_parser pipeline and calls ``NormalizedConcentration.matches()``.
If the parse fails (DB value unreadable) the candidate is rejected safely.

Usage
-----
    async with AsyncSessionLocal() as session:
        parsed   = parse("Acetaminofen 325mg Tableta")
        result   = await match_drug(session, parsed, hospital_id="SANITAS")
        print(result.stage, result.confidence)
"""
from __future__ import annotations

import logging
import unicodedata
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Float, Index, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy import func, select
from sqlmodel import Field, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.services.drug_parser import (
    ConcEncoding,
    FormGroup,
    NormalizedConcentration,
    ParsedDrug,
    ParseWarningCode,
    _layer3_normalize_form,
    _parse_bracket_concentration,
    _parse_inline_dose,
)
from app.models.medicamento import Medicamento, MedicamentoCUM

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration constants (tune via environment/config in production)
# ---------------------------------------------------------------------------

#: Minimum pg_trgm similarity for the INN field in Stage 2.
#: Applied in SQL — Python concentration hard barrier is the enforcer.
TRGM_INN_THRESHOLD: float = 0.85

#: Maximum candidates retrieved by Stage 2 SQL (before Python filtering).
STAGE2_CANDIDATE_LIMIT: int = 20

#: Form similarity threshold for Stage 2 (applied in Python, not SQL).
FORM_TRGM_SOFT_THRESHOLD: float = 0.60


# ---------------------------------------------------------------------------
# Synonym dictionary model  (TODO: move to app/models/ + run alembic migration)
# ---------------------------------------------------------------------------

class DrugSynonymDictEntry(SQLModel, table=True):
    """
    Hospital-scoped synonym dictionary.  Every time a human resolves a
    NO_MATCH or MATCH_FUZZY_SAFE result, the mapping is stored here.
    On subsequent runs for the same hospital the lookup is O(1) exact.
    """

    __tablename__ = "drug_synonym_dict"
    __table_args__ = (
        Index(
            "ix_drug_synonym_dict_hospital_raw",
            "hospital_id",
            "raw_input_normalized",
            unique=True,
        ),
    )

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True),
    )
    hospital_id:            str = Field(sa_column=Column(String, nullable=False, index=True))
    raw_input:              str = Field(sa_column=Column(String, nullable=False))
    raw_input_normalized:   str = Field(sa_column=Column(String, nullable=False))
    cum_id:                 str = Field(sa_column=Column(String, nullable=False, index=True))
    medicamento_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(PGUUID(as_uuid=True), nullable=True),
    )
    resolved_by:    str = Field(sa_column=Column(String, nullable=False, default="HUMAN"))
    confidence:   float = Field(sa_column=Column(Float, nullable=False, default=1.0))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=False), nullable=False),
    )


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------

class MatchStage(str, Enum):
    SYNONYM_DICT   = "SYNONYM_DICT"    # Pre-stage: exact dictionary hit
    EXACT          = "EXACT"           # S1: exact SQL match
    FUZZY_INN_SAFE = "FUZZY_INN_SAFE"  # S2: pg_trgm INN + hard concentration barrier
    NO_MATCH       = "NO_MATCH"        # S3: no candidate survived all hard barriers


class RejectReason(str, Enum):
    CONCENTRATION_MISMATCH      = "CONCENTRATION_MISMATCH"
    CONCENTRATION_PARSE_FAILED  = "CONCENTRATION_PARSE_FAILED"
    FORM_GROUP_MISMATCH         = "FORM_GROUP_MISMATCH"
    INN_SIMILARITY_TOO_LOW      = "INN_SIMILARITY_TOO_LOW"
    DRUG_INACTIVE               = "DRUG_INACTIVE"
    INPUT_NOT_MATCHABLE         = "INPUT_NOT_MATCHABLE"
    NO_CANDIDATES               = "NO_CANDIDATES"


class MatchResult:
    """
    Fully auditable match result.

    All fields are set regardless of stage so that every result can be
    written to a structured audit log without further manipulation.
    """

    def __init__(
        self,
        stage:               MatchStage,
        confidence:          float,
        cum_id:              Optional[str]  = None,
        medicamento_id:      Optional[UUID] = None,
        db_principio_activo: Optional[str]  = None,
        db_forma:            Optional[str]  = None,
        db_concentracion:    Optional[str]  = None,
        inn_score:           Optional[float]= None,
        reject_reason:       Optional[RejectReason] = None,
        closest_candidate:   Optional[dict[str, Any]] = None,
        parser_warnings:     Optional[list[str]]      = None,
    ) -> None:
        self.stage               = stage
        self.confidence          = confidence
        self.cum_id              = cum_id
        self.medicamento_id      = medicamento_id
        self.db_principio_activo = db_principio_activo
        self.db_forma            = db_forma
        self.db_concentracion    = db_concentracion
        self.inn_score           = inn_score
        self.reject_reason       = reject_reason
        self.closest_candidate   = closest_candidate
        self.parser_warnings     = parser_warnings or []

    def __repr__(self) -> str:
        return (
            f"MatchResult(stage={self.stage!r}, confidence={self.confidence:.3f}, "
            f"cum_id={self.cum_id!r}, inn_score={self.inn_score!r})"
        )


# ---------------------------------------------------------------------------
# Concentration hard barrier — Python-side enforcement
# ---------------------------------------------------------------------------

def _parse_db_concentration(raw_conc: Optional[str]) -> Optional[NormalizedConcentration]:
    """
    Re-parse a raw concentration string from medicamentos_cum.concentracion
    using the same drug_parser pipeline.

    Returns None if the string cannot be parsed — which causes the candidate
    to be safely rejected (fail-closed behavior).
    """
    if not raw_conc or not raw_conc.strip():
        return None

    warnings: list[str] = []
    cleaned = raw_conc.strip()

    # Try inline dose format: "325 mg", "5mg/mL", "25000 IU/mL", etc.
    conc = _parse_inline_dose(cleaned, warnings)
    if conc:
        return conc

    # Try bracket format (some legacy records wrap concentration in brackets)
    bracket_inner = cleaned.strip("[]").strip()
    conc = _parse_bracket_concentration(bracket_inner, warnings)
    return conc  # None if still unparseable


def _concentration_hard_barrier(
    parsed_drug:  ParsedDrug,
    db_conc_raw:  Optional[str],
    component_idx: int = 0,
) -> tuple[bool, Optional[RejectReason]]:
    """
    Enforce the concentration hard barrier for one component.

    Returns
    -------
    (passes, reject_reason)
        ``passes=True`` means the concentration is EXACTLY equivalent.
        ``passes=False`` means the candidate MUST be rejected, regardless
        of how high its INN trigram similarity is.

    Safety contract
    ---------------
    - If the DB concentration cannot be parsed → REJECT (fail-closed).
    - If the parsed drug has no concentration stored → REJECT.
    - If value or unit differ even by 0.001 → REJECT.
    """
    if not parsed_drug.concentrations:
        return False, RejectReason.CONCENTRATION_PARSE_FAILED

    # For mono-drugs use the canonical concentration; for combos use by index
    if parsed_drug.is_combo:
        if component_idx >= len(parsed_drug.concentrations):
            return False, RejectReason.CONCENTRATION_MISMATCH
        query_conc = parsed_drug.concentrations[component_idx]
    else:
        query_conc = parsed_drug.canonical_concentration
        if query_conc is None:
            return False, RejectReason.CONCENTRATION_PARSE_FAILED

    db_conc = _parse_db_concentration(db_conc_raw)
    if db_conc is None:
        return False, RejectReason.CONCENTRATION_PARSE_FAILED

    if not query_conc.matches(db_conc):
        return False, RejectReason.CONCENTRATION_MISMATCH

    return True, None


# ---------------------------------------------------------------------------
# Form group hard barrier — Python-side enforcement
# ---------------------------------------------------------------------------

def _normalize_db_form(raw_form: Optional[str]) -> tuple[Optional[str], Optional[FormGroup]]:
    """Normalize a DB forma_farmaceutica string through the same Layer 3 pipeline."""
    if not raw_form:
        return None, None
    # Strip diacritics for lookup
    nfkd = unicodedata.normalize("NFKD", raw_form)
    ascii_f = nfkd.encode("ascii", "ignore").decode("ascii").strip().lower()
    return _layer3_normalize_form(ascii_f, [])


def _form_group_barrier(
    query_form_group: Optional[FormGroup],
    db_form_raw:      Optional[str],
) -> tuple[bool, Optional[RejectReason]]:
    """
    Reject candidates whose pharmaceutical form belongs to a different
    administration-route group.

    A cross-group match (e.g. 'solucion inyectable' vs 'solucion oral')
    is ALWAYS rejected, even with a perfect INN and dose match.
    This prevents a clinically dangerous route-of-administration mismatch.
    """
    if query_form_group is None:
        # No form extracted from input — skip form group check
        return True, None

    _, db_form_group = _normalize_db_form(db_form_raw)

    if db_form_group is None or db_form_group == FormGroup.OTHER:
        # DB form unrecognized — skip group check, proceed cautiously
        return True, None

    if query_form_group != db_form_group:
        return False, RejectReason.FORM_GROUP_MISMATCH

    return True, None


# ---------------------------------------------------------------------------
# INN query string builder
# ---------------------------------------------------------------------------

def _build_inn_query(drug: ParsedDrug) -> str:
    """
    Construct the INN string to be sent to pg_trgm similarity().

    For mono-drugs:  "acetaminofen"
    For combos:      sorted, "/" separated — mirrors INVIMA catalog convention
                     e.g. "acetaminofen / codeina"
    """
    inns = sorted(c.canonical_inn for c in drug.components)
    return " / ".join(inns)


# ---------------------------------------------------------------------------
# Stage 1 — Exact SQL match
# ---------------------------------------------------------------------------

async def _stage1_exact(
    session:    AsyncSession,
    drug:       ParsedDrug,
    inn_query:  str,
) -> Optional[tuple]:
    """
    Exact match on principio_activo (case-insensitive) and forma_farmaceutica.
    Concentration checked in Python after retrieval.

    Returns the first row whose concentration passes the hard barrier,
    or None if no row survives.
    """
    canonical_form = drug.canonical_form or ""

    stmt = (
        select(
            Medicamento.id,
            Medicamento.id_cum,
            Medicamento.principio_activo,
            Medicamento.forma_farmaceutica,
            Medicamento.nombre_limpio,
            MedicamentoCUM.concentracion,
        )
        .outerjoin(MedicamentoCUM, Medicamento.id_cum == MedicamentoCUM.id_cum)
        .where(
            func.lower(func.coalesce(Medicamento.principio_activo, "")) == inn_query
        )
        .where(
            func.lower(func.coalesce(Medicamento.forma_farmaceutica, "")) == canonical_form
        )
        .where(Medicamento.activo == True)  # noqa: E712
        .limit(10)
    )

    rows = (await session.exec(stmt)).all()

    for row in rows:
        passes, reason = _concentration_hard_barrier(drug, row.concentracion)
        if passes:
            return row

    return None


# ---------------------------------------------------------------------------
# Stage 2 — pg_trgm fuzzy match  +  Python concentration hard barrier
# ---------------------------------------------------------------------------

async def _stage2_fuzzy(
    session:    AsyncSession,
    drug:       ParsedDrug,
    inn_query:  str,
) -> tuple[Optional[tuple], Optional[float]]:
    """
    Fuzzy INN match via pg_trgm similarity ≥ TRGM_INN_THRESHOLD.
    Concentration checked in Python (hard barrier).
    Form-group checked in Python (hard barrier).

    Returns (best_row, inn_score) or (None, None) if no row survives.

    SQL design notes
    ----------------
    - ``similarity()`` requires pg_trgm extension (already installed).
    - ``func.similarity(col, literal)`` produces a GiST/GIN index scan when
      combined with the threshold operator; explicit LIMIT caps cost.
    - The concentration WHERE clause is intentionally NOT in SQL — we need
      to re-parse the DB concentration string in Python to guarantee the
      same normalization logic is applied to both sides.
    """
    stmt = (
        select(
            Medicamento.id,
            Medicamento.id_cum,
            Medicamento.principio_activo,
            Medicamento.forma_farmaceutica,
            Medicamento.nombre_limpio,
            MedicamentoCUM.concentracion,
            func.similarity(
                func.lower(func.coalesce(Medicamento.principio_activo, "")),
                inn_query,
            ).label("inn_score"),
        )
        .outerjoin(MedicamentoCUM, Medicamento.id_cum == MedicamentoCUM.id_cum)
        .where(
            func.similarity(
                func.lower(func.coalesce(Medicamento.principio_activo, "")),
                inn_query,
            ) > TRGM_INN_THRESHOLD
        )
        .where(Medicamento.activo == True)  # noqa: E712
        .order_by(text("inn_score DESC"))
        .limit(STAGE2_CANDIDATE_LIMIT)
    )

    rows = (await session.exec(stmt)).all()

    best_row:   Optional[tuple] = None
    best_score: float           = 0.0

    for row in rows:
        # ── Hard Barrier 1: Pharmaceutical form group ──────────────────────
        form_ok, form_reason = _form_group_barrier(drug.form_group, row.forma_farmaceutica)
        if not form_ok:
            logger.debug(
                "Stage 2 form-group barrier rejected CUM=%s (%s vs %s): %s",
                row.id_cum, drug.form_group, row.forma_farmaceutica, form_reason,
            )
            continue

        # ── Hard Barrier 2: Concentration (parse DB value, compare exactly) ─
        conc_ok, conc_reason = _concentration_hard_barrier(drug, row.concentracion)
        if not conc_ok:
            logger.debug(
                "Stage 2 concentration barrier rejected CUM=%s "
                "(query=%s, db_raw=%r): %s",
                row.id_cum,
                drug.canonical_concentration,
                row.concentracion,
                conc_reason,
            )
            continue

        # ── Candidate survived both barriers ───────────────────────────────
        score = float(row.inn_score)
        if score > best_score:
            best_score = score
            best_row   = row

    if best_row is None:
        return None, None

    return best_row, best_score


# ---------------------------------------------------------------------------
# Synonym dictionary lookup  (pre-stage, O(1))
# ---------------------------------------------------------------------------

def _normalize_for_dict(raw: str) -> str:
    """Produce the lookup key for the synonym dictionary."""
    nfkd = unicodedata.normalize("NFKD", raw)
    ascii_s = nfkd.encode("ascii", "ignore").decode("ascii").strip().lower()
    import re
    return re.sub(r"\s+", " ", ascii_s)


async def _check_synonym_dict(
    session:     AsyncSession,
    raw_input:   str,
    hospital_id: str,
) -> Optional[MatchResult]:
    """
    Check the hospital-scoped synonym dictionary.

    Returns a populated MatchResult if a match is found, otherwise None.
    The result bypasses all normalization stages — this is intentional:
    the mapping was already validated by a human.
    """
    normalized_key = _normalize_for_dict(raw_input)

    stmt = (
        select(DrugSynonymDictEntry)
        .where(DrugSynonymDictEntry.hospital_id            == hospital_id)
        .where(DrugSynonymDictEntry.raw_input_normalized   == normalized_key)
        .limit(1)
    )
    entry = (await session.exec(stmt)).first()
    if entry is None:
        return None

    return MatchResult(
        stage=MatchStage.SYNONYM_DICT,
        confidence=entry.confidence,
        cum_id=entry.cum_id,
        medicamento_id=entry.medicamento_id,
    )


# ---------------------------------------------------------------------------
# Public matching entry point
# ---------------------------------------------------------------------------

async def match_drug(
    session:     AsyncSession,
    drug:        ParsedDrug,
    hospital_id: str = "GLOBAL",
) -> MatchResult:
    """
    Run the full matching pipeline for one ParsedDrug.

    Parameters
    ----------
    session     : SQLAlchemy async session (catalog DB)
    drug        : Output of ``drug_parser.parse()``
    hospital_id : Scopes the synonym dictionary lookup.
                  Use a stable hospital identifier e.g. "SANITAS".

    Returns
    -------
    MatchResult
        Always returns a value.  Inspect ``.stage`` to understand the
        outcome; inspect ``.reject_reason`` if ``.stage == NO_MATCH``.

    Pipeline
    --------
    1. Check synonym dictionary (O(1) exact lookup, hospital-scoped)
    2. Stage 1 — Exact INN + form SQL match, concentration in Python
    3. Stage 2 — pg_trgm INN fuzzy + form-group guard + concentration Python
    4. NO_MATCH: structured alert with closest candidate for human review
    """
    parser_warnings = list(drug.parse_warnings)

    # ── Guard: refuse to match a drug with a blocking parse warning ──────────
    if not drug.is_matchable:
        logger.warning(
            "match_drug: input not matchable (blocking warnings=%s): %r",
            drug.parse_warnings,
            drug.raw_input,
        )
        return MatchResult(
            stage=MatchStage.NO_MATCH,
            confidence=0.0,
            reject_reason=RejectReason.INPUT_NOT_MATCHABLE,
            parser_warnings=parser_warnings,
        )

    # ── PRE: Synonym dictionary ───────────────────────────────────────────────
    dict_result = await _check_synonym_dict(session, drug.raw_input, hospital_id)
    if dict_result is not None:
        dict_result.parser_warnings = parser_warnings
        logger.debug("match_drug: SYNONYM_DICT hit for %r", drug.raw_input)
        return dict_result

    inn_query = _build_inn_query(drug)
    logger.debug("match_drug: inn_query=%r  form=%r", inn_query, drug.canonical_form)

    # ── Stage 1: Exact SQL match ──────────────────────────────────────────────
    row = await _stage1_exact(session, drug, inn_query)
    if row is not None:
        logger.debug("match_drug: EXACT hit  cum_id=%s", row.id_cum)
        return MatchResult(
            stage=MatchStage.EXACT,
            confidence=1.0,
            cum_id=row.id_cum,
            medicamento_id=row.id,
            db_principio_activo=row.principio_activo,
            db_forma=row.forma_farmaceutica,
            db_concentracion=row.concentracion,
            inn_score=1.0,
            parser_warnings=parser_warnings,
        )

    # ── Stage 2: pg_trgm fuzzy ────────────────────────────────────────────────
    best_row, best_score = await _stage2_fuzzy(session, drug, inn_query)
    if best_row is not None and best_score is not None:
        logger.debug(
            "match_drug: FUZZY_INN_SAFE hit  cum_id=%s  score=%.3f",
            best_row.id_cum, best_score,
        )
        return MatchResult(
            stage=MatchStage.FUZZY_INN_SAFE,
            confidence=best_score,
            cum_id=best_row.id_cum,
            medicamento_id=best_row.id,
            db_principio_activo=best_row.principio_activo,
            db_forma=best_row.forma_farmaceutica,
            db_concentracion=best_row.concentracion,
            inn_score=best_score,
            parser_warnings=parser_warnings,
        )

    # ── Stage 3: NO_MATCH — build closest-candidate record for review queue ──
    logger.info("match_drug: NO_MATCH for %r", drug.raw_input)
    closest = await _get_closest_candidate_for_review(session, inn_query)
    return MatchResult(
        stage=MatchStage.NO_MATCH,
        confidence=0.0,
        reject_reason=RejectReason.NO_CANDIDATES if closest is None else RejectReason.CONCENTRATION_MISMATCH,
        closest_candidate=closest,
        parser_warnings=parser_warnings,
    )


async def _get_closest_candidate_for_review(
    session:   AsyncSession,
    inn_query: str,
) -> Optional[dict[str, Any]]:
    """
    Retrieve the closest candidate from the DB for the human review queue.
    This is called only for NO_MATCH results and has no clinical impact.
    The candidate is informational only — it NEVER auto-resolves a match.
    """
    stmt = (
        select(
            Medicamento.id,
            Medicamento.id_cum,
            Medicamento.principio_activo,
            Medicamento.forma_farmaceutica,
            MedicamentoCUM.concentracion,
            func.similarity(
                func.lower(func.coalesce(Medicamento.principio_activo, "")),
                inn_query,
            ).label("inn_score"),
        )
        .outerjoin(MedicamentoCUM, Medicamento.id_cum == MedicamentoCUM.id_cum)
        .where(Medicamento.activo == True)  # noqa: E712
        .order_by(text("inn_score DESC"))
        .limit(1)
    )
    try:
        row = (await session.exec(stmt)).first()
    except Exception as exc:
        logger.debug("_get_closest_candidate_for_review failed: %s", exc)
        return None

    if row is None:
        return None

    return {
        "cum_id":           row.id_cum,
        "medicamento_id":   str(row.id),
        "principio_activo": row.principio_activo,
        "forma_farmaceutica": row.forma_farmaceutica,
        "concentracion":    row.concentracion,
        "inn_score":        float(row.inn_score),
    }


# ---------------------------------------------------------------------------
# Synonym dictionary writer  (called by human review resolution workflow)
# ---------------------------------------------------------------------------

async def record_synonym_resolution(
    session:        AsyncSession,
    hospital_id:    str,
    raw_input:      str,
    cum_id:         str,
    medicamento_id: Optional[UUID] = None,
    resolved_by:    str            = "HUMAN",
    confidence:     float          = 1.0,
) -> DrugSynonymDictEntry:
    """
    Persist a confirmed match to the synonym dictionary.

    Call this from the review dashboard when an operator resolves a
    NO_MATCH or FUZZY_INN_SAFE result.  Subsequent runs for the same
    hospital will hit the dictionary directly (PRE stage, O(1)).
    """
    entry = DrugSynonymDictEntry(
        hospital_id           = hospital_id,
        raw_input             = raw_input,
        raw_input_normalized  = _normalize_for_dict(raw_input),
        cum_id                = cum_id,
        medicamento_id        = medicamento_id,
        resolved_by           = resolved_by,
        confidence            = confidence,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    logger.info(
        "Synonym recorded: hospital=%s  raw=%r  cum_id=%s",
        hospital_id, raw_input, cum_id,
    )
    return entry
