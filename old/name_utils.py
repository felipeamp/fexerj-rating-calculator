"""Utility functions for player name normalisation and comparison."""
import unicodedata

from rapidfuzz import fuzz


def normalize_name(name):
    """Lowercase, strip accents, remove commas, sort tokens — for name comparison."""
    nfkd = unicodedata.normalize('NFKD', name)
    ascii_name = nfkd.encode('ascii', 'ignore').decode('ascii')
    tokens = sorted(ascii_name.lower().replace(',', '').split())
    return ' '.join(tokens)


def name_similarity(name_a, name_b):
    return fuzz.ratio(normalize_name(name_a), normalize_name(name_b))
