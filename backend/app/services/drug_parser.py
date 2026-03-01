"""Surgical Drug Name Parser — Genhospi Bulk Quoting Engine.

Implements the deterministic 4-layer normalization pipeline defined in the
Technical Design Document (2026-02-28).  No ML models, no heuristics that
can produce silent errors: every transformation is traceable and auditable.

Public API
----------
    result: ParsedDrug = parse("Acetaminofen + Codeina 325mg + 15mg Tableta")

Layer summary
-------------
    Layer 0  Pre-flight sanitization (Unicode NFC, lowercase, keep semantic chars)
    Layer 1  Structural segmentation (bracket/paren extraction, form detection,
             combo splitting, INN/dose token classification)
    Layer 2  Value normalization (locale-aware number parsing, unit canonicalization,
             ratio simplification, % ↔ mg/mL arithmetic validation)
    Layer 3  Pharmaceutical form normalization (synonym ontology → canonical code)
"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ParseWarningCode(str, Enum):
    """Machine-readable codes attached to ParsedDrug.parse_warnings."""
    AMBIGUOUS_DECIMAL           = "AMBIGUOUS_DECIMAL"
    BRACKET_RATIO_INCONSISTENT  = "BRACKET_RATIO_INCONSISTENT"
    COMPONENT_COUNT_MISMATCH    = "COMPONENT_COUNT_MISMATCH"
    FORM_NOT_RECOGNIZED         = "FORM_NOT_RECOGNIZED"
    INN_NOT_IN_SYNONYM_TABLE    = "INN_NOT_IN_SYNONYM_TABLE"
    NO_CONCENTRATION_FOUND      = "NO_CONCENTRATION_FOUND"
    PAREN_SYNONYM_UNRESOLVED    = "PAREN_SYNONYM_UNRESOLVED"
    UNPARSEABLE_BRACKET         = "UNPARSEABLE_BRACKET"


class ConcEncoding(str, Enum):
    """How the concentration value was encoded in the original string."""
    INLINE          = "inline"           # "325mg"
    INLINE_PERCENT  = "inline_percent"   # "2%"
    BRACKET_SIMPLE  = "bracket_simple"   # "[500mg]"
    BRACKET_RATIO   = "bracket_ratio"    # "[100mg/5mL]" → simplified to mg/mL


class FormGroup(str, Enum):
    """Administration-route group.  Matches across groups are ALWAYS rejected."""
    ORAL_SOLID      = "ORAL_SOLID"
    ORAL_LIQUID     = "ORAL_LIQUID"
    INJECTABLE      = "INJECTABLE"
    TOPICAL         = "TOPICAL"
    OPHTHALMIC      = "OPHTHALMIC"
    INHALATION      = "INHALATION"
    RECTAL_VAGINAL  = "RECTAL_VAGINAL"
    OTHER           = "OTHER"


# ---------------------------------------------------------------------------
# Static lookup tables (version-controlled here; migrate to DB as volume grows)
# ---------------------------------------------------------------------------

# --- Unit canonical map: lower-case input → canonical output ---------------
_UNIT_CANONICAL: dict[str, str] = {
    # Mass
    "mg":           "mg",
    "g":            "g",
    "mcg":          "mcg",
    "µg":           "mcg",
    "microgramo":   "mcg",
    "microgramos":  "mcg",
    "ug":           "mcg",
    # International Units
    "ui":           "IU",
    "iu":           "IU",
    "u":            "IU",
    "usp":          "IU",
    "miu":          "mIU",
    # Volume
    "ml":           "mL",
    "l":            "L",
    # Electrolytes
    "meq":          "mEq",
    "mmol":         "mmol",
    # Percentage
    "%":            "%",
    # Compound: mass / volume
    "mg/ml":        "mg/mL",
    "mg/dl":        "mg/dL",
    "mg/l":         "mg/L",
    "mg/g":         "mg/g",
    "mg/kg":        "mg/kg",
    "g/ml":         "g/mL",
    "g/dl":         "g/dL",
    "g/l":          "g/L",
    "g/g":          "g/g",
    "mcg/ml":       "mcg/mL",
    "ug/ml":        "mcg/mL",
    "µg/ml":        "mcg/mL",
    "mcg/kg":       "mcg/kg",
    "ui/ml":        "IU/mL",
    "iu/ml":        "IU/mL",
    "ui/g":         "IU/g",
    "iu/g":         "IU/g",
    "meq/ml":       "mEq/mL",
    "meq/l":        "mEq/L",
    "mmol/ml":      "mmol/mL",
    "mmol/l":       "mmol/L",
}

# Ordered longest-first so that greedy matching works (e.g. "mg/mL" before "mg")
_UNIT_PATTERN_ORDERED: list[tuple[str, str]] = sorted(
    _UNIT_CANONICAL.items(),
    key=lambda kv: len(kv[0]),
    reverse=True,
)

# --- INN synonym table: raw normalized input → canonical INN ---------------
# Scope: Colombian pharmaceutical market / Latin American INN conventions.
# Rule: prefer INVIMA catalog spelling (the DB side) as canonical.
_INN_SYNONYMS: dict[str, str] = {
    # Vitamins & common synonyms
    "vitamina d3":          "colecalciferol",
    "vitamin d3":           "colecalciferol",
    "cholecalciferol":      "colecalciferol",
    "colecalciferol":       "colecalciferol",
    "vitamina b12":         "cianocobalamina",
    "cianocobalamina":      "cianocobalamina",
    "vitamina b1":          "tiamina",
    "tiamina":              "tiamina",
    "vitamina c":           "acido ascorbico",
    "acido ascorbico":      "acido ascorbico",
    "acido folico":         "acido folico",
    "folato":               "acido folico",
    # NSAIDs / analgesics — NOTE: INVIMA uses "acetaminofen" (Colombian norm)
    "paracetamol":          "acetaminofen",
    "acetaminofen":         "acetaminofen",
    # Antibiotics
    "amoxicilina":          "amoxicilina",
    "amoxycillin":          "amoxicilina",
    "acido clavulanico":    "acido clavulanico",
    "ac clavulanico":       "acido clavulanico",
    "ac. clavulanico":      "acido clavulanico",
    "clavulanato":          "acido clavulanico",
    "azitromicina":         "azitromicina",
    "claritromicina":       "claritromicina",
    "ciprofloxacino":       "ciprofloxacino",
    "ciprofloxacina":       "ciprofloxacino",
    "metronidazol":         "metronidazol",
    # Antivirals
    "abacavir":             "abacavir",
    "aciclovir":            "aciclovir",
    "acyclovir":            "aciclovir",
    # Opioids
    "codeina":              "codeina",
    "codeína":              "codeina",
    "tramadol":             "tramadol",
    "morfina":              "morfina",
    # Other common drugs
    "agua destilada":       "agua para preparaciones inyectables",
    "agua esteril":         "agua para preparaciones inyectables",
    "agua destilada esteril": "agua para preparaciones inyectables",
}

# --- Pharmaceutical form synonym table → canonical form --------------------
_FORM_SYNONYMS: dict[str, str] = {
    # Oral solids
    "tableta":                              "tableta",
    "tabletas":                             "tableta",
    "tab":                                  "tableta",
    "tab.":                                 "tableta",
    "comprimido":                           "tableta",
    "comprimidos":                          "tableta",
    "tableta recubierta":                   "tableta recubierta",
    "tableta dispersable":                  "tableta dispersable",
    "tableta efervescente":                 "tableta efervescente",
    "capsula":                              "capsula",
    "capsulas":                             "capsula",
    "cap":                                  "capsula",
    "cap.":                                 "capsula",
    "capsula de liberacion prolongada":     "capsula de liberacion prolongada",
    "capsula de liberacion modificada":     "capsula de liberacion modificada",
    "gragea":                               "gragea",
    "ovulo":                                "ovulo",          # dual: oral or vaginal — context required
    # Oral liquids
    "solucion oral":                        "solucion oral",
    "sol. oral":                            "solucion oral",
    "solucion":                             "solucion oral",  # only when no route qualifier follows
    "suspension oral":                      "suspension oral",
    "suspension":                           "suspension oral",
    "jarabe":                               "jarabe",
    "syrup":                                "jarabe",
    "elixir":                               "elixir",
    "emulsion oral":                        "emulsion oral",
    "gotas orales":                         "gotas orales",
    # Injectables
    "solucion inyectable":                  "solucion inyectable",
    "solucion para inyeccion":              "solucion inyectable",
    "sol. inyectable":                      "solucion inyectable",
    "solucion para infusion":               "solucion para infusion",
    "solucion para infusion intravenosa":   "solucion para infusion",
    "polvo para solucion inyectable":       "polvo para solucion inyectable",
    "polvo para reconstitucion":            "polvo para reconstitucion",
    "liofilizado":                          "polvo para reconstitucion",
    "suspension inyectable":                "suspension inyectable",
    # Topicals
    "unguento topico":                      "unguento",
    "unguento":                             "unguento",
    "ungüento":                             "unguento",
    "ungüento topico":                      "unguento",
    "crema topica":                         "crema",
    "crema":                                "crema",
    "gel topico":                           "gel topico",
    "gel":                                  "gel topico",
    "solucion topica":                      "solucion topica",
    "locion":                               "locion",
    "espuma topica":                        "espuma topica",
    "parche transdermico":                  "parche transdermico",
    # Ophthalmic
    "solucion oftalmica":                   "solucion oftalmica",
    "colirio":                              "solucion oftalmica",
    "gotas oftalmicas":                     "solucion oftalmica",
    "suspension oftalmica":                 "suspension oftalmica",
    # Inhalation
    "inhalador":                            "inhalador",
    "aerosol":                              "inhalador",
    "spray nasal":                          "spray nasal",
    "spray":                                "inhalador",
    "polvo para inhalacion":                "polvo para inhalacion",
    # Rectal / vaginal
    "supositorio":                          "supositorio",
    "supositorios":                         "supositorio",
    "ovulo vaginal":                        "ovulo vaginal",
}

# --- Form → FormGroup mapping ----------------------------------------------
_FORM_GROUP: dict[str, FormGroup] = {
    "tableta":                              FormGroup.ORAL_SOLID,
    "tableta recubierta":                   FormGroup.ORAL_SOLID,
    "tableta dispersable":                  FormGroup.ORAL_SOLID,
    "tableta efervescente":                 FormGroup.ORAL_SOLID,
    "capsula":                              FormGroup.ORAL_SOLID,
    "capsula de liberacion prolongada":     FormGroup.ORAL_SOLID,
    "capsula de liberacion modificada":     FormGroup.ORAL_SOLID,
    "gragea":                               FormGroup.ORAL_SOLID,
    "solucion oral":                        FormGroup.ORAL_LIQUID,
    "suspension oral":                      FormGroup.ORAL_LIQUID,
    "jarabe":                               FormGroup.ORAL_LIQUID,
    "elixir":                               FormGroup.ORAL_LIQUID,
    "emulsion oral":                        FormGroup.ORAL_LIQUID,
    "gotas orales":                         FormGroup.ORAL_LIQUID,
    "solucion inyectable":                  FormGroup.INJECTABLE,
    "solucion para infusion":               FormGroup.INJECTABLE,
    "polvo para solucion inyectable":       FormGroup.INJECTABLE,
    "polvo para reconstitucion":            FormGroup.INJECTABLE,
    "suspension inyectable":                FormGroup.INJECTABLE,
    "unguento":                             FormGroup.TOPICAL,
    "crema":                                FormGroup.TOPICAL,
    "gel topico":                           FormGroup.TOPICAL,
    "solucion topica":                      FormGroup.TOPICAL,
    "locion":                               FormGroup.TOPICAL,
    "espuma topica":                        FormGroup.TOPICAL,
    "parche transdermico":                  FormGroup.TOPICAL,
    "solucion oftalmica":                   FormGroup.OPHTHALMIC,
    "suspension oftalmica":                 FormGroup.OPHTHALMIC,
    "inhalador":                            FormGroup.INHALATION,
    "spray nasal":                          FormGroup.INHALATION,
    "polvo para inhalacion":                FormGroup.INHALATION,
    "supositorio":                          FormGroup.RECTAL_VAGINAL,
    "ovulo vaginal":                        FormGroup.RECTAL_VAGINAL,
    "ovulo":                                FormGroup.RECTAL_VAGINAL,
}

# Known forms sorted longest-first for greedy right-anchor matching
_KNOWN_FORMS_SORTED: list[str] = sorted(
    _FORM_SYNONYMS.keys(),
    key=len,
    reverse=True,
)

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# Bracket content:  [...]
_BRACKET_RE = re.compile(r"\[([^\]]*)\]")
# Parenthetical content: (...)
_PAREN_RE = re.compile(r"\(([^)]*)\)")

# Bracket concentration: ratio form  100mg/5mL  (must match BEFORE simple form)
# Both sides have a number.
_BRACKET_RATIO_RE = re.compile(
    r"""
    (?P<num1>\d+(?:[.,]\d+)?)     # numerator value
    \s*
    (?P<unit1>
        mg|mcg|µg|ug|g\b|UI|IU|mEq|mmol|mL|ml|L\b
    )
    \s*/\s*
    (?P<num2>\d+(?:[.,]\d+)?)     # denominator value
    \s*
    (?P<unit2>
        mL|ml|g\b|L\b
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Inline dose token:  325mg  /  25,000UI/mL  /  2%
# The denominator of compound units (e.g. mg/mL) does NOT have a leading number.
_UNIT_COMPOUND_SORTED = "|".join(
    re.escape(u)
    for u, _ in _UNIT_PATTERN_ORDERED
    if "/" in u
)
_UNIT_SIMPLE_SORTED = "|".join(
    re.escape(u)
    for u, _ in _UNIT_PATTERN_ORDERED
    if "/" not in u
)

_INLINE_DOSE_RE = re.compile(
    rf"""
    (?P<num>\d+(?:[.,]\d+)?)      # value (may contain decimal comma or thousands comma)
    \s*
    (?P<unit>
        {_UNIT_COMPOUND_SORTED}   # compound units first (longer match wins)
      | {_UNIT_SIMPLE_SORTED}     # then simple units
    )
    (?!\w)                        # not followed by a word character
                                  # (replaces \b which breaks for non-word units like %)
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Split on " + " that is NOT inside brackets or parentheses.
# We use a character-level splitter (see _split_on_plus below) for full safety.

# Trailing whitespace-padded splitter for "+" used outside delimiters
_PLUS_RE = re.compile(r"\s*\+\s*")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class NormalizedConcentration(BaseModel):
    """
    A single, fully normalized concentration value.

    Examples
    --------
    "325mg"          → value=325,   unit="mg",     encoding=INLINE
    "2%"             → value=2,     unit="%",      encoding=INLINE_PERCENT
    "[100mg/5mL]"    → value=20,    unit="mg/mL",  encoding=BRACKET_RATIO
    "25,000UI/mL"    → value=25000, unit="IU/mL",  encoding=INLINE
    """

    raw: str = Field(description="Verbatim token from the input string")
    value: Decimal = Field(description="Numeric magnitude, locale-resolved")
    unit: str = Field(description="Canonical unit string e.g. 'mg', 'mg/mL', 'IU/mL'")
    encoding: ConcEncoding = Field(description="How this concentration was encoded in the source")

    model_config = {"frozen": True}

    def matches(self, other: "NormalizedConcentration") -> bool:
        """Strict equality check used as the Hard Barrier in the matching engine."""
        return self.value == other.value and self.unit.lower() == other.unit.lower()

    def __str__(self) -> str:
        return f"{self.value} {self.unit}"


class DrugComponent(BaseModel):
    """One active principle in a (possibly combo) drug."""

    raw_inn: str = Field(description="INN text after Layer 0 normalization")
    canonical_inn: str = Field(
        description=(
            "Canonical INN resolved through the synonym table. "
            "Equals raw_inn if no synonym entry exists."
        )
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Trade names / synonym names extracted from parentheticals",
    )

    model_config = {"frozen": True}


class ParsedDrug(BaseModel):
    """
    The complete output of the normalization pipeline for one input row.

    Design invariant
    ----------------
    ``len(components) == len(concentrations)`` UNLESS a ParseWarningCode
    is present in ``parse_warnings``.  The matching engine must refuse to
    proceed if COMPONENT_COUNT_MISMATCH is in parse_warnings.
    """

    raw_input: str
    components: list[DrugComponent] = Field(default_factory=list)
    concentrations: list[NormalizedConcentration] = Field(default_factory=list)
    canonical_form: Optional[str] = Field(default=None)
    raw_form: Optional[str] = Field(default=None)
    form_group: Optional[FormGroup] = Field(default=None)
    component_count: int = Field(default=0)
    is_combo: bool = Field(default=False)
    parse_warnings: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def sync_component_count(self) -> "ParsedDrug":
        object.__setattr__(self, "component_count", len(self.components))
        object.__setattr__(self, "is_combo", len(self.components) > 1)
        return self

    @property
    def canonical_concentration(self) -> Optional[NormalizedConcentration]:
        """
        Return the single most precise concentration for a mono-component drug.
        Prefers BRACKET_RATIO (already simplified) over INLINE_PERCENT.
        Returns None for combo drugs or when no concentration was found.
        """
        if self.is_combo or not self.concentrations:
            return None
        priority = {
            ConcEncoding.BRACKET_RATIO: 0,
            ConcEncoding.INLINE: 1,
            ConcEncoding.BRACKET_SIMPLE: 2,
            ConcEncoding.INLINE_PERCENT: 3,
        }
        return min(self.concentrations, key=lambda c: priority.get(c.encoding, 99))

    @property
    def is_matchable(self) -> bool:
        """
        True when this ParsedDrug can be safely sent to the matching engine.
        Returns False when a blocking warning (COMPONENT_COUNT_MISMATCH or
        AMBIGUOUS_DECIMAL) is present.
        """
        blocking = {
            ParseWarningCode.COMPONENT_COUNT_MISMATCH,
            ParseWarningCode.AMBIGUOUS_DECIMAL,
        }
        return not any(w in self.parse_warnings for w in blocking)


# ---------------------------------------------------------------------------
# Layer 0 — Pre-flight sanitization
# ---------------------------------------------------------------------------

def _layer0_sanitize(raw: str) -> str:
    """
    Produce a clean, encoding-safe string for the segmentation layer.

    Preserves ALL semantically load-bearing characters: %, [], (), +, /
    Only normalizes encoding and casing — never removes structural chars.
    """
    if not raw or not raw.strip():
        return ""
    # NFC normalization: compose precomposed characters (é not e + combining ́)
    normalized = unicodedata.normalize("NFC", raw)
    return normalized.strip().lower()


# ---------------------------------------------------------------------------
# Layer 1 — Structural segmentation helpers
# ---------------------------------------------------------------------------

def _extract_delimited_blocks(text: str) -> tuple[str, list[str], list[str]]:
    """
    Extract all [bracket] and (paren) blocks from *text*.

    Returns
    -------
    cleaned_text : str
        Input with all delimited blocks removed and whitespace collapsed.
    bracket_contents : list[str]
        Raw content strings from each [...] block (in order of appearance).
    paren_contents : list[str]
        Raw content strings from each (...) block (in order of appearance).
    """
    bracket_contents: list[str] = [m.group(1).strip() for m in _BRACKET_RE.finditer(text)]
    paren_contents:   list[str] = [m.group(1).strip() for m in _PAREN_RE.finditer(text)]

    cleaned = _BRACKET_RE.sub(" ", text)
    cleaned = _PAREN_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned, bracket_contents, paren_contents


def _extract_trailing_form(text: str) -> tuple[str, Optional[str]]:
    """
    Identify and strip a pharmaceutical form from the right end of *text*.

    Tries each known form from longest to shortest (greedy).
    Returns (remaining_text, raw_form_found).
    """
    lower = text.lower().rstrip()
    for form in _KNOWN_FORMS_SORTED:
        if lower.endswith(form):
            remaining = text[: len(lower) - len(form)].strip()
            return remaining, form
    return text.strip(), None


def _split_on_plus_outside_delimiters(text: str) -> list[str]:
    """
    Split *text* on '+' only when the '+' is NOT inside brackets or parens.
    Works by tracking delimiter depth — prevents splitting inside [amox + clav].
    """
    segments: list[str] = []
    current: list[str] = []
    depth = 0
    for ch in text:
        if ch in "([":
            depth += 1
            current.append(ch)
        elif ch in ")]":
            depth = max(depth - 1, 0)
            current.append(ch)
        elif ch == "+" and depth == 0:
            segments.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    tail = "".join(current).strip()
    if tail:
        segments.append(tail)
    return [s for s in segments if s]


def _split_inn_and_dose(segment: str) -> tuple[str, Optional[str]]:
    """
    Within a single segment (after '+' splitting), locate the first inline
    dose token.  Everything before it is the INN text; the dose token and
    everything after is the raw dose string.

    Returns
    -------
    inn_part  : str   (may be empty — e.g. for a pure-dose segment like "15mg")
    dose_part : str | None
    """
    match = _INLINE_DOSE_RE.search(segment)
    if match:
        inn_part  = segment[: match.start()].strip()
        dose_part = segment[match.start() :].strip()
        return inn_part, dose_part
    return segment.strip(), None


def _resolve_paren_synonym(
    paren_content: str,
    raw_inn: str,
) -> tuple[str, list[str]]:
    """
    Determine the canonical INN and alias list when a parenthetical synonym
    was found.

    Priority:
        1. If the paren content exists in _INN_SYNONYMS → use as canonical
        2. If raw_inn exists in _INN_SYNONYMS → use synonym table entry
        3. Otherwise keep raw_inn as canonical and paren_content as alias
    """
    paren_lower = paren_content.strip().lower()
    raw_lower   = raw_inn.strip().lower()

    if paren_lower in _INN_SYNONYMS:
        canonical = _INN_SYNONYMS[paren_lower]
        aliases   = [raw_inn] if raw_lower != canonical else []
        return canonical, aliases

    if raw_lower in _INN_SYNONYMS:
        canonical = _INN_SYNONYMS[raw_lower]
        aliases   = [paren_content] if paren_lower != canonical else []
        return canonical, aliases

    # Neither recognized — keep raw_inn, add paren as alias
    return raw_lower, [paren_content]


# ---------------------------------------------------------------------------
# Layer 2 — Value normalization
# ---------------------------------------------------------------------------

def _resolve_decimal_locale(num_str: str, unit: str, warnings: list[str]) -> Decimal:
    """
    Resolve European decimal comma vs. US thousands separator comma.

    Rules
    -----
    1. No comma present → parse directly (may contain a dot)
    2. Comma followed by exactly 3 digits (e.g. "25,000") → thousands separator → "25000"
    3. Comma followed by 1 or 2 digits (e.g. "37,5") → decimal separator → "37.5"
    4. Comma followed by ≥ 4 digits → decimal (unusual; flag as AMBIGUOUS_DECIMAL)
    5. Multiple commas → flag as AMBIGUOUS_DECIMAL and fall through to best-effort parse
    """
    cleaned = num_str.replace(" ", "")

    if "," not in cleaned:
        try:
            return Decimal(cleaned.replace(",", "."))
        except InvalidOperation:
            warnings.append(ParseWarningCode.AMBIGUOUS_DECIMAL)
            return Decimal("0")

    parts = cleaned.split(",")

    if len(parts) == 2:
        before, after = parts
        if len(after) == 3 and after.isdigit():
            # Thousands separator: "25,000" → 25000
            return Decimal(before + after)
        elif len(after) in (1, 2):
            # Decimal comma: "37,5" → 37.5
            return Decimal(before + "." + after)
        elif len(after) >= 4:
            # Ambiguous — flag and attempt decimal interpretation
            warnings.append(ParseWarningCode.AMBIGUOUS_DECIMAL)
            try:
                return Decimal(before + "." + after)
            except InvalidOperation:
                return Decimal("0")

    # Multiple commas or other weird format
    warnings.append(ParseWarningCode.AMBIGUOUS_DECIMAL)
    try:
        return Decimal(cleaned.replace(",", ""))
    except InvalidOperation:
        return Decimal("0")


def _canonicalize_unit(raw_unit: str) -> str:
    """Return the canonical unit string; falls back to uppercase raw if unknown."""
    return _UNIT_CANONICAL.get(raw_unit.strip().lower(), raw_unit.strip().upper())


def _parse_inline_dose(
    dose_str: str,
    warnings: list[str],
) -> Optional[NormalizedConcentration]:
    """
    Parse an inline dose string like "325mg", "2%", "25,000UI/mL".
    Returns None if the string cannot be parsed.
    """
    m = _INLINE_DOSE_RE.search(dose_str)
    if not m:
        return None

    raw_unit = m.group("unit")
    encoding = (
        ConcEncoding.INLINE_PERCENT
        if raw_unit.strip() == "%"
        else ConcEncoding.INLINE
    )
    value = _resolve_decimal_locale(m.group("num"), raw_unit, warnings)
    unit  = _canonicalize_unit(raw_unit)
    return NormalizedConcentration(raw=dose_str, value=value, unit=unit, encoding=encoding)


def _parse_bracket_concentration(
    bracket_content: str,
    warnings: list[str],
) -> Optional[NormalizedConcentration]:
    """
    Parse a bracket concentration string.

    Two forms are recognized:
    - Ratio:  "100mg/5mL" → simplify to 20mg/mL  (BRACKET_RATIO)
    - Simple: "500mg"     → keep as-is            (BRACKET_SIMPLE)
    """
    m_ratio = _BRACKET_RATIO_RE.fullmatch(bracket_content.strip())
    if m_ratio:
        v1 = _resolve_decimal_locale(m_ratio.group("num1"), m_ratio.group("unit1"), warnings)
        v2 = _resolve_decimal_locale(m_ratio.group("num2"), m_ratio.group("unit2"), warnings)
        u1 = _canonicalize_unit(m_ratio.group("unit1"))
        u2 = _canonicalize_unit(m_ratio.group("unit2"))

        if v2 == 0:
            warnings.append(ParseWarningCode.UNPARSEABLE_BRACKET)
            return None

        # Simplify ratio → canonical compound unit  (e.g. 100mg/5mL → 20 mg/mL)
        simplified_value = v1 / v2
        canonical_unit   = f"{u1}/{u2}"
        # Normalize compound unit through synonym table
        canonical_unit   = _canonicalize_unit(canonical_unit)

        return NormalizedConcentration(
            raw=bracket_content,
            value=simplified_value.normalize(),
            unit=canonical_unit,
            encoding=ConcEncoding.BRACKET_RATIO,
        )

    # Try simple bracket form
    m_simple = _INLINE_DOSE_RE.search(bracket_content)
    if m_simple:
        value = _resolve_decimal_locale(m_simple.group("num"), m_simple.group("unit"), warnings)
        unit  = _canonicalize_unit(m_simple.group("unit"))
        return NormalizedConcentration(
            raw=bracket_content,
            value=value,
            unit=unit,
            encoding=ConcEncoding.BRACKET_SIMPLE,
        )

    warnings.append(ParseWarningCode.UNPARSEABLE_BRACKET)
    return None


def _validate_percent_vs_bracket(
    pct_conc: NormalizedConcentration,
    bracket_conc: NormalizedConcentration,
    warnings: list[str],
) -> None:
    """
    Assert arithmetic consistency between a percentage and a simplified
    bracket ratio for the same drug (e.g. 2% should equal 20 mg/mL).

    Only checks cases where the bracket unit is mg/mL and % represents g/100mL.
    Logs a warning but does NOT raise — the matching engine will choose the
    canonical (bracket) form regardless.
    """
    if bracket_conc.unit != "mg/mL":
        return
    # 1 % (w/v) = 10 mg/mL  →  pct_value * 10 should equal bracket_value
    expected = pct_conc.value * Decimal("10")
    if abs(expected - bracket_conc.value) > Decimal("0.01") * bracket_conc.value:
        warnings.append(ParseWarningCode.BRACKET_RATIO_INCONSISTENT)


def _normalize_inn_text(raw: str) -> str:
    """
    Produce a search-normalized INN string:
    - Remove diacritics for ASCII matching
    - Collapse whitespace
    - Strip pharmaceutical qualifiers that are not part of the INN

    NOTE: does NOT lowercase here — that is already done in Layer 0.
    """
    # Remove diacritics (keep for display, strip for matching)
    nfkd = unicodedata.normalize("NFKD", raw)
    ascii_inn = nfkd.encode("ascii", "ignore").decode("ascii")

    # Strip common salt / qualifier suffixes (not INN-defining in catalog)
    qualifier_re = re.compile(
        r"\b(?:clorhidrato|hidrocloruro|sodico|potasico|calcico|acetato|"
        r"fosfato|sulfato|bromuro|maleato|fumarato|tartrato|base)\b",
        re.IGNORECASE,
    )
    ascii_inn = qualifier_re.sub(" ", ascii_inn)
    return re.sub(r"\s{2,}", " ", ascii_inn).strip().lower()


def _build_drug_component(
    raw_inn_text: str,
    paren_synonyms: list[str],
    warnings: list[str],
) -> DrugComponent:
    """
    Construct a DrugComponent, resolving the canonical INN.

    Lookup order:
        1. Paren synonym → INN synonyms table
        2. Raw INN → INN synonyms table
        3. Paren synonym kept as alias, raw INN used as canonical
        4. If nothing recognized → raw INN used, flag warning
    """
    normalized_raw = _normalize_inn_text(raw_inn_text)
    aliases: list[str] = []

    if paren_synonyms:
        canonical, aliases = _resolve_paren_synonym(paren_synonyms[0], normalized_raw)
    elif normalized_raw in _INN_SYNONYMS:
        canonical = _INN_SYNONYMS[normalized_raw]
        if canonical != normalized_raw:
            aliases = [normalized_raw]
    else:
        canonical = normalized_raw
        warnings.append(ParseWarningCode.INN_NOT_IN_SYNONYM_TABLE)

    return DrugComponent(raw_inn=normalized_raw, canonical_inn=canonical, aliases=aliases)


# ---------------------------------------------------------------------------
# Layer 3 — Pharmaceutical form normalization
# ---------------------------------------------------------------------------

def _layer3_normalize_form(
    raw_form: Optional[str],
    warnings: list[str],
) -> tuple[Optional[str], Optional[FormGroup]]:
    """
    Map the raw form string to its canonical form and FormGroup.
    Normalizes diacritics before lookup.
    """
    if not raw_form:
        return None, None

    nfkd    = unicodedata.normalize("NFKD", raw_form)
    ascii_f = nfkd.encode("ascii", "ignore").decode("ascii").strip().lower()
    # Collapse internal whitespace
    ascii_f = re.sub(r"\s+", " ", ascii_f)

    canonical = _FORM_SYNONYMS.get(ascii_f)
    if canonical is None:
        warnings.append(ParseWarningCode.FORM_NOT_RECOGNIZED)
        return raw_form, FormGroup.OTHER

    return canonical, _FORM_GROUP.get(canonical, FormGroup.OTHER)


# ---------------------------------------------------------------------------
# Public parse() entry point
# ---------------------------------------------------------------------------

def parse(raw: str) -> ParsedDrug:
    """
    Full 4-layer normalization pipeline for a single pharmaceutical product
    description string.

    Parameters
    ----------
    raw : str
        Free-text product name, e.g.
        "Acetaminofen + Codeina 325mg + 15mg Tableta"

    Returns
    -------
    ParsedDrug
        Structured, normalized representation.  Always returns a value —
        errors are communicated through ``parse_warnings``, never raised.
    """
    warnings: list[str] = []

    # ── Layer 0 ──────────────────────────────────────────────────────────────
    sanitized = _layer0_sanitize(raw)
    if not sanitized:
        return ParsedDrug(raw_input=raw, parse_warnings=[ParseWarningCode.NO_CONCENTRATION_FOUND])

    # ── Layer 1: structural segmentation ─────────────────────────────────────

    # 1a. Extract and remove delimited blocks
    after_delimiters, bracket_contents, paren_contents = _extract_delimited_blocks(sanitized)

    # 1b. Extract trailing pharmaceutical form (right-anchored)
    after_form, raw_form = _extract_trailing_form(after_delimiters)

    # 1c. Split on + outside delimiters
    segments = _split_on_plus_outside_delimiters(after_form)
    if not segments:
        segments = [after_form]

    # 1d. Per segment: separate INN from dose
    inn_parts:  list[str] = []
    dose_parts: list[str] = []

    for seg in segments:
        inn_text, dose_text = _split_inn_and_dose(seg)
        if inn_text:
            inn_parts.append(inn_text)
        if dose_text:
            dose_parts.append(dose_text)

    # 1e. Collect inline concentrations (from dose_parts)
    inline_concentrations: list[NormalizedConcentration] = []
    for dose_str in dose_parts:
        conc = _parse_inline_dose(dose_str, warnings)
        if conc:
            inline_concentrations.append(conc)

    # 1f. Parse bracket concentrations
    bracket_concentrations: list[NormalizedConcentration] = []
    for bc in bracket_contents:
        conc = _parse_bracket_concentration(bc, warnings)
        if conc:
            bracket_concentrations.append(conc)

    # ── Layer 2: value normalization ─────────────────────────────────────────

    # 2a. If both % and bracket ratio present on a mono-drug, validate
    pct_concs     = [c for c in inline_concentrations if c.encoding == ConcEncoding.INLINE_PERCENT]
    bracket_ratio = next((c for c in bracket_concentrations if c.encoding == ConcEncoding.BRACKET_RATIO), None)
    if pct_concs and bracket_ratio:
        _validate_percent_vs_bracket(pct_concs[0], bracket_ratio, warnings)

    # 2b. Choose the canonical concentration set:
    #   - For mono-drug with BOTH inline and bracket: use bracket_ratio as primary,
    #     keep the inline form as secondary (matching engine uses canonical_concentration)
    #   - For combo drugs: each component gets one inline concentration
    #   - For bracket without inline: use bracket only
    if len(inn_parts) > 1:
        # Combo drug: concentrations order matches inn_parts order
        all_concentrations = inline_concentrations
    else:
        # Single drug: prefer bracket_ratio, keep all variants
        all_concentrations = bracket_concentrations + inline_concentrations

    if not all_concentrations:
        warnings.append(ParseWarningCode.NO_CONCENTRATION_FOUND)

    # 2c. Build DrugComponent objects
    components: list[DrugComponent] = []
    for i, inn_raw in enumerate(inn_parts):
        # Assign parenthetical synonyms to the first (and usually only) INN
        parens = paren_contents if i == 0 else []
        comp   = _build_drug_component(inn_raw, parens, warnings)
        components.append(comp)

    # 2d. For combo drugs, validate component ↔ concentration parity
    if len(components) > 1 and len(inline_concentrations) != len(components):
        warnings.append(ParseWarningCode.COMPONENT_COUNT_MISMATCH)

    # If no INN was extracted at all, use the full sanitized text
    if not components:
        comp = _build_drug_component(after_form or sanitized, paren_contents, warnings)
        components = [comp]

    # ── Layer 3: form normalization ──────────────────────────────────────────
    canonical_form, form_group = _layer3_normalize_form(raw_form, warnings)

    return ParsedDrug(
        raw_input=raw,
        components=components,
        concentrations=all_concentrations,
        canonical_form=canonical_form,
        raw_form=raw_form,
        form_group=form_group,
        parse_warnings=warnings,
    )


# ---------------------------------------------------------------------------
# __main__ : assertion-based test suite
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from decimal import Decimal

    def _assert(condition: bool, message: str) -> None:
        if not condition:
            raise AssertionError(f"FAIL: {message}")
        print(f"  PASS  {message}")

    print("\n========== drug_parser.py — Sanitas Sample Test Suite ==========\n")

    # ─── Test 1: Dual Concentration — Abacavir ───────────────────────────────
    print("Test 1: Abacavir 2% [100mg/5mL] Solucion oral")
    r1 = parse("Abacavir 2% [100mg/5mL] Solucion oral")

    _assert(r1.component_count == 1,
            "T1: exactly one component")
    _assert(r1.components[0].canonical_inn == "abacavir",
            f"T1: canonical INN == 'abacavir' (got '{r1.components[0].canonical_inn}')")
    _assert(r1.canonical_form == "solucion oral",
            f"T1: form == 'solucion oral' (got '{r1.canonical_form}')")
    _assert(r1.form_group == FormGroup.ORAL_LIQUID,
            f"T1: form_group == ORAL_LIQUID (got '{r1.form_group}')")
    # Canonical concentration should be the bracket ratio (most precise)
    _assert(r1.canonical_concentration is not None,
            "T1: canonical_concentration is not None")
    _assert(r1.canonical_concentration.encoding == ConcEncoding.BRACKET_RATIO,
            f"T1: canonical encoding == BRACKET_RATIO (got '{r1.canonical_concentration.encoding}')")
    _assert(r1.canonical_concentration.value == Decimal("20"),
            f"T1: 100mg/5mL simplified == 20 mg/mL (got {r1.canonical_concentration.value})")
    _assert(r1.canonical_concentration.unit == "mg/mL",
            f"T1: canonical unit == 'mg/mL' (got '{r1.canonical_concentration.unit}')")
    # Both concentrations stored (bracket + inline %)
    _assert(len(r1.concentrations) == 2,
            f"T1: two concentrations stored (bracket + %) (got {len(r1.concentrations)})")
    _assert(
        ParseWarningCode.BRACKET_RATIO_INCONSISTENT not in r1.parse_warnings,
        "T1: no arithmetic inconsistency warning (2% == 20mg/mL is correct)",
    )
    print()

    # ─── Test 2: Combo Interleaved — Acetaminofen + Codeina ──────────────────
    print("Test 2: Acetaminofen + Codeina 325mg + 15mg Tableta")
    r2 = parse("Acetaminofen + Codeina 325mg + 15mg Tableta")

    _assert(r2.is_combo,
            "T2: is_combo == True")
    _assert(r2.component_count == 2,
            f"T2: component_count == 2 (got {r2.component_count})")
    _assert(r2.components[0].canonical_inn == "acetaminofen",
            f"T2: first INN == 'acetaminofen' (got '{r2.components[0].canonical_inn}')")
    _assert(r2.components[1].canonical_inn == "codeina",
            f"T2: second INN == 'codeina' (got '{r2.components[1].canonical_inn}')")
    _assert(r2.concentrations[0].value == Decimal("325"),
            f"T2: first dose == 325 mg (got {r2.concentrations[0].value})")
    _assert(r2.concentrations[0].unit == "mg",
            f"T2: first unit == 'mg' (got '{r2.concentrations[0].unit}')")
    _assert(r2.concentrations[1].value == Decimal("15"),
            f"T2: second dose == 15 mg (got {r2.concentrations[1].value})")
    _assert(r2.concentrations[1].unit == "mg",
            f"T2: second unit == 'mg' (got '{r2.concentrations[1].unit}')")
    _assert(r2.canonical_form == "tableta",
            f"T2: form == 'tableta' (got '{r2.canonical_form}')")
    _assert(r2.form_group == FormGroup.ORAL_SOLID,
            f"T2: form_group == ORAL_SOLID (got '{r2.form_group}')")
    _assert(ParseWarningCode.COMPONENT_COUNT_MISMATCH not in r2.parse_warnings,
            "T2: no COMPONENT_COUNT_MISMATCH warning")
    print()

    # ─── Test 3: Combo — Acetaminofen + Tramadol (European decimal comma) ────
    print("Test 3: Acetaminofen + Tramadol 325mg + 37,5mg Tableta")
    r3 = parse("Acetaminofen + Tramadol 325mg + 37,5mg Tableta")

    _assert(r3.is_combo, "T3: is_combo == True")
    _assert(r3.components[0].canonical_inn == "acetaminofen",
            f"T3: first INN == 'acetaminofen' (got '{r3.components[0].canonical_inn}')")
    _assert(r3.components[1].canonical_inn == "tramadol",
            f"T3: second INN == 'tramadol' (got '{r3.components[1].canonical_inn}')")
    _assert(r3.concentrations[0].value == Decimal("325"),
            f"T3: 325mg parsed correctly (got {r3.concentrations[0].value})")
    _assert(r3.concentrations[1].value == Decimal("37.5"),
            f"T3: 37,5mg (European decimal) → 37.5 (got {r3.concentrations[1].value})")
    _assert(ParseWarningCode.AMBIGUOUS_DECIMAL not in r3.parse_warnings,
            "T3: '37,5' correctly resolved as decimal (1 digit after comma)")
    print()

    # ─── Test 4: Parenthetical synonym — Vitamina D3 (colecalciferol) ────────
    print("Test 4: Vitamina D3 (colecalciferol) 25,000UI/mL Solucion oral")
    r4 = parse("Vitamina D3 (colecalciferol) 25,000UI/mL Solucion oral")

    _assert(r4.component_count == 1, "T4: single component")
    _assert(r4.components[0].canonical_inn == "colecalciferol",
            f"T4: canonical INN promoted to 'colecalciferol' (got '{r4.components[0].canonical_inn}')")
    _assert("vitamina d3" in r4.components[0].aliases or r4.components[0].raw_inn == "vitamina d3",
            f"T4: 'vitamina d3' retained as alias or raw_inn (got raw='{r4.components[0].raw_inn}', "
            f"aliases={r4.components[0].aliases})")
    _assert(r4.concentrations[0].value == Decimal("25000"),
            f"T4: 25,000 (thousands separator) → 25000 (got {r4.concentrations[0].value})")
    _assert(r4.concentrations[0].unit == "IU/mL",
            f"T4: UI/mL canonicalized to 'IU/mL' (got '{r4.concentrations[0].unit}')")
    _assert(ParseWarningCode.AMBIGUOUS_DECIMAL not in r4.parse_warnings,
            "T4: '25,000' correctly resolved as thousands separator")
    print()

    # ─── Test 5: Topical percentage — Aciclovir 5% [500mg/10g] ──────────────
    print("Test 5: Aciclovir 5% [500mg/10g] Unguento topico")
    r5 = parse("Aciclovir 5% [500mg/10g] Unguento topico")

    _assert(r5.components[0].canonical_inn == "aciclovir",
            f"T5: canonical INN == 'aciclovir' (got '{r5.components[0].canonical_inn}')")
    _assert(r5.canonical_concentration is not None, "T5: canonical_concentration is not None")
    _assert(r5.canonical_concentration.value == Decimal("50"),
            f"T5: 500mg/10g → 50 mg/g (got {r5.canonical_concentration.value})")
    _assert(r5.canonical_concentration.unit == "mg/g",
            f"T5: unit == 'mg/g' (got '{r5.canonical_concentration.unit}')")
    _assert(r5.canonical_form == "unguento",
            f"T5: 'unguento topico' normalized to 'unguento' (got '{r5.canonical_form}')")
    _assert(r5.form_group == FormGroup.TOPICAL,
            f"T5: form_group == TOPICAL (got '{r5.form_group}')")
    print()

    # ─── Test 6: Volume-as-concentration — Agua destilada esteril 10mL ───────
    print("Test 6: Agua destilada esteril 10mL Solucion inyectable")
    r6 = parse("Agua destilada esteril 10mL Solucion inyectable")

    _assert("agua" in r6.components[0].raw_inn,
            f"T6: INN contains 'agua' (got '{r6.components[0].raw_inn}')")
    _assert(r6.concentrations[0].value == Decimal("10"),
            f"T6: 10mL extracted (got {r6.concentrations[0].value})")
    _assert(r6.concentrations[0].unit == "mL",
            f"T6: unit == 'mL' (got '{r6.concentrations[0].unit}')")
    _assert(r6.canonical_form == "solucion inyectable",
            f"T6: form == 'solucion inyectable' (got '{r6.canonical_form}')")
    _assert(r6.form_group == FormGroup.INJECTABLE,
            f"T6: form_group == INJECTABLE (got '{r6.form_group}')")
    print()

    # ─── Test 7: Hard Barrier — 325mg vs 500mg MUST NOT match ────────────────
    print("Test 7: Hard Barrier — concentration mismatch detection")
    r7a = parse("Acetaminofen 325mg Tableta")
    r7b = parse("Acetaminofen 500mg Tableta")

    can_a = r7a.canonical_concentration
    can_b = r7b.canonical_concentration

    _assert(can_a is not None and can_b is not None,
            "T7: both have a canonical concentration")
    _assert(not can_a.matches(can_b),
            f"T7: 325mg.matches(500mg) == False — Hard Barrier enforced! "
            f"(got {can_a}.matches({can_b}))")
    _assert(can_a.matches(can_a),
            "T7: 325mg.matches(325mg) == True — same dose matches itself")
    print()

    print("========== ALL TESTS PASSED ==========\n")
