"""Configuration for the pytest test suite."""

from __future__ import annotations

import warnings

# pikvm-lib 0.5.0's keymaps.py contains an invalid escape sequence ("\s")
# that emits a SyntaxWarning at compile time. With pytest's
# filterwarnings=error policy this becomes a SyntaxError during test
# collection on fresh installs (CI). Pre-import the offending module with
# the warning suppressed so subsequent test-time imports hit the module
# cache and never re-compile.
with warnings.catch_warnings():
    # Suppress both SyntaxWarning (Python 3.12+) and DeprecationWarning
    # (Python 3.10/3.11) — the category for invalid string escapes changed.
    warnings.simplefilter("ignore")
    import pikvm_lib.keymaps  # noqa: F401
