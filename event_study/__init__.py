"""
event_study -- the canonical event-study framework for this repository.

Built for H11 (point-in-time PEAD), but deliberately not H11-specific. Every
module in this package operates only on the `Event` contract defined in
schemas.py. A future hypothesis (H12 and beyond) that can produce a list of
`Event` records gets universe construction, matched-control benchmarking,
cost modeling, and diagnostics for free -- only the event-generation logic
(which lives in `hypotheses/<name>/event_generator.py`, outside this
package) needs to be hypothesis-specific.

See results/H11_IMPLEMENTATION_SPEC.md for the full architecture writeup
this package implements.
"""
from __future__ import annotations
