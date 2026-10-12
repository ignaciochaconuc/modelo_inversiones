"""Small, diagnosed editorial equivalences; never a generic synonym system."""
from __future__ import annotations

import re
import unicodedata


RULES = ("iphone_number_spacing", "soft_sluggish_demand", "terminal_nikkei_credit")


def normalize_editorial_headline(text: str, rules: tuple[str, ...] = RULES) -> str:
    """Preserve products, generations, figures, states and negation.

    Only a terminal dash-delimited Nikkei credit is accessory; references to
    Nikkei inside a proposition, or any other suffix, remain substantive.
    Demand equivalence is phrase-local, not a sentiment feature.
    """
    value = unicodedata.normalize("NFKC", text).casefold()
    if "iphone_number_spacing" in rules:
        value = re.sub(r"\biphone(?=\d+\b)", "iphone ", value)
    if "soft_sluggish_demand" in rules:
        value = re.sub(r"\bsluggish\s+demand\b", "soft demand", value)
    if "terminal_nikkei_credit" in rules:
        value = re.sub(r"\s*[-\u2013\u2014]\s*nikkei\s*$", "", value)
    return value


def normalize_product_spacing(text: str) -> str:
    """Expose iPhone generation digits to factual guards, without synonyms."""
    return normalize_editorial_headline(text, ("iphone_number_spacing",))
