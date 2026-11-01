"""Market-entry facts layer for the last-mile / e-fulfillment case (C2).

``Facts`` is a frozen, pure-Python dataclass: one named market figure per
field, every field carrying its confidence tag (CONFIRMED / EST / VERIFY)
and a source note so the number is traceable. Nothing here fetches —
the case runs offline; the notebook reads these constants and the model
is a pure function over them, which is what makes the test suite able to
lock every behaviour.
"""
from .facts import Facts, OPERATORS, measured_fields
from .sanity import cross_check

__all__ = ["Facts", "OPERATORS", "measured_fields", "cross_check"]
