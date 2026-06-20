"""Analyst Booth — grounded data slice + append-only commentary log.

The booth watches the auction draft and produces running commentary. This
package holds the deterministic, testable Python pieces:

- ``slice``: builds an ``AnalystSlice`` (neutral facts only) from the data dir
  and renders a compact text brief for the host to forward.
- ``log``: the ``AnalystComment`` schema plus an atomic append and a defensive
  reader for ``data/analyst-comments.jsonl``.

The host orchestration (watch loop, curation gate, persona relay) lives in an
LLM playbook, not here.
"""
