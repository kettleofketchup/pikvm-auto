# Screenshot + OCR library for PiKVM.
#
# Covers /api/streamer/snapshot in both raw-frame and OCR modes, plus a
# fuzzy-match polling helper (wait_for_text).
#
# HTTP wiring
# -----------
# pikvm-lib 0.5.0's BuildPiKVM does NOT use a requests.Session. Upstream calls
# the module-level requests.get / requests.post functions directly with
# headers=self.headers and verify=self.certificate_trusted on every call.
# ScreenshotClient follows the same pattern: it reads headers, hostname,
# schema, and certificate_trusted from the passed PiKVM instance and calls
# the module-level requests.get directly. Tests must monkeypatch
# pikvm_auto._internal.commands.screenshot.requests.get rather than any
# session attribute.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from pathlib import Path

    from pikvm_lib.pikvm import PiKVM

try:
    from rapidfuzz import fuzz as _fuzz

    _HAVE_RAPIDFUZZ = True
except ImportError:
    _HAVE_RAPIDFUZZ = False
    import difflib


@dataclass
class ScreenMatch:
    """Result of a fuzzy screen-text match.

    Fields:
      matched:  True if the final score was at or above the threshold.
      score:    Final similarity score in [0.0, 1.0].
      expected: Expected text that was searched for.
      ocr_text: Last OCR'd screen text observed.
      elapsed:  Total time spent polling, in seconds.
      captures: Any screenshot files saved during polling.
    """

    matched: bool
    score: float
    expected: str
    ocr_text: str
    elapsed: float
    captures: list[Path] = field(default_factory=list)


def fuzzy_score(
    expected: str,
    actual: str,
    *,
    case_sensitive: bool = False,
) -> float:
    """Return a substring-aware fuzzy similarity score in [0.0, 1.0].

    Uses ``rapidfuzz.fuzz.partial_ratio`` when available (handles substring
    matches and OCR character-level errors). Falls back to a ``difflib``
    ``SequenceMatcher`` sliding window if rapidfuzz isn't installed.
    """
    if not expected:
        return 1.0
    if not actual:
        return 0.0
    e, a = (expected, actual) if case_sensitive else (expected.lower(), actual.lower())

    if _HAVE_RAPIDFUZZ:
        return _fuzz.partial_ratio(e, a) / 100.0

    # Fallback: sliding window of len(expected) over actual
    elen = len(e)
    if elen >= len(a):
        return difflib.SequenceMatcher(None, e, a).ratio()
    best = 0.0
    for i in range(len(a) - elen + 1):
        chunk = a[i : i + elen]
        r = difflib.SequenceMatcher(None, e, chunk).ratio()
        best = max(best, r)
        if best >= 1.0:
            break
    return best


class ScreenshotClient:
    """Client for /api/streamer/snapshot + OCR.

    Reads ``headers``, ``hostname``, ``schema``, and ``certificate_trusted``
    from the passed ``PiKVM`` instance and calls the module-level
    ``requests.get`` directly (matching pikvm-lib's own pattern — see the
    module comment block at the top of this file).
    """

    def __init__(self, pikvm: PiKVM) -> None:
        self._headers = pikvm.headers
        self._base = f"{pikvm.schema}://{pikvm.hostname}"
        self._verify = pikvm.certificate_trusted

    def capture(self, *, ocr: bool = False) -> bytes:
        """Fetch a screenshot via ``/api/streamer/snapshot``.

        With ``ocr=True`` the response Content-Type is ``text/plain`` (the
        kvmd OCR result); otherwise it is ``image/jpeg`` binary data.
        """
        params: dict[str, str] = {}
        if ocr:
            params["ocr"] = "true"
        resp = requests.get(
            f"{self._base}/api/streamer/snapshot",
            params=params,
            headers=self._headers,
            verify=self._verify,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.content
