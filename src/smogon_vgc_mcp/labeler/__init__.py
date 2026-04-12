"""Offline labeling workstation for historical VGC article extraction eval.

Produces golden-set ground-truth JSON files used to score the Haiku 4.5
extractor via per-slot F1. Not part of the MCP server runtime — exposed
as the separate ``vgc-label`` CLI behind the ``labeler`` extras.
"""
