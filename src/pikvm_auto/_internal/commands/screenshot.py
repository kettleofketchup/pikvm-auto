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

if TYPE_CHECKING:
    from pathlib import Path

    from pikvm_lib.pikvm import PiKVM


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
    """Return a fuzzy similarity score in [0.0, 1.0].

    Stub — real implementation lands in Task 2.2.
    """
    raise NotImplementedError


class ScreenshotClient:
    """Client for /api/streamer/snapshot (stub — real impl in Task 2.3)."""

    def __init__(self, pikvm: PiKVM) -> None:
        self._pk = pikvm
