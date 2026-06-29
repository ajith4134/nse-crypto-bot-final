"""Vendored Generative-Agents "Memory Stream" (Stanford joonspk-research).

Source: https://github.com/joonspk-research/generative_agents (Apache-2.0)
See memory_stream.py header for the exact files extracted and the minimal
decoupling edits (injected importance_fn / embed_fn / synthesize_fn).

Public API:
    AssociativeMemory / MemoryStream  -- the memory stream
    ConceptNode                       -- a single memory record
    default_importance_fn, default_embed_fn, default_synthesize_fn
    cos_sim, normalize_dict_floats, top_highest_x_values  -- retrieval math
"""

from .memory_stream import (
    AssociativeMemory,
    MemoryStream,
    ConceptNode,
    cos_sim,
    normalize_dict_floats,
    top_highest_x_values,
    extract_recency,
    extract_importance,
    extract_relevance,
    default_importance_fn,
    default_embed_fn,
    default_synthesize_fn,
)

__all__ = [
    "AssociativeMemory",
    "MemoryStream",
    "ConceptNode",
    "cos_sim",
    "normalize_dict_floats",
    "top_highest_x_values",
    "extract_recency",
    "extract_importance",
    "extract_relevance",
    "default_importance_fn",
    "default_embed_fn",
    "default_synthesize_fn",
]
