"""WordNet, when it is installed, and a warning once when it is not.

The validator's linting and the lemma matcher use WordNet (through nltk) for a
few judgements: whether a name's head is a physical thing, whether two glosses
are near in meaning. Without it those checks quietly fell back, so a checkout
without nltk gave different warnings from one with it and said nothing (the
simulated maintainer and the code review, 2026-10-22). Now the first use says
so, once, on stderr.

    pip install -e ".[wordnet]"
    python -m nltk.downloader wordnet
"""
from __future__ import annotations

import sys

_WN = None
_WARNED = False


def wordnet():
    """nltk's WordNet corpus reader, or None (with one warning) if nltk or its
    WordNet data is missing."""
    global _WN, _WARNED
    if _WN is not None:
        return _WN
    try:
        from nltk.corpus import wordnet as wn
        wn.synsets("dog")                     # the corpus itself, not just the package
        _WN = wn
        return wn
    except Exception as e:                                       # noqa: BLE001
        if not _WARNED:
            _WARNED = True
            print(f"note: WordNet is not available ({type(e).__name__}), so the checks that use it are skipped "
                  "and some results differ. To add it: pip install -e \".[wordnet]\" and "
                  "python -m nltk.downloader wordnet", file=sys.stderr)
        return None
