"""
Generative Agents "Memory Stream" -- vendored, decoupled, offline-capable.

SOURCE (vendored, not reimplemented):
    Joon Sung Park et al., "Generative Agents: Interactive Simulacra of
    Human Behavior" (Stanford).
    Repo:    https://github.com/joonspk-research/generative_agents
    License: Apache License 2.0
    Files extracted/merged:
      - reverie/backend_server/persona/memory_structures/associative_memory.py
            (ConceptNode, AssociativeMemory.add_event / add_thought)
      - reverie/backend_server/persona/cognitive_modules/retrieve.py
            (cos_sim, normalize_dict_floats, top_highest_x_values,
             extract_recency / extract_importance / extract_relevance,
             new_retrieve scoring)
      - reverie/backend_server/persona/cognitive_modules/reflect.py
            (reflection_trigger / run_reflect insight-synthesis loop)

The original code is tightly coupled to a running LLM server (OpenAI) and to a
`persona` object (scratch hyper-parameters + a_mem). The ONLY edits made here:

    1. Removed the hard dependency on numpy: `cos_sim` is reimplemented in pure
       Python (math.sqrt) so the module imports with zero third-party deps and
       does no network I/O at import time.
    2. Removed the hard dependency on an LLM / embedding API. Importance
       (poignancy) and embeddings are now INJECTED callables:
           importance_fn(text) -> int (1..10)
           embed_fn(text)      -> list[float]
       Both default to deterministic offline heuristics (see below) so the
       module works completely offline.
    3. The persona's `scratch` hyper-parameters (recency_w, relevance_w,
       importance_w, recency_decay, importance_trigger_max) are now plain
       constructor arguments with the SAME default values as Stanford's
       scratch.py (1, 1, 1, 0.99, 150).
    4. Reflection synthesis (which originally called GPT) is injected as
       `synthesize_fn(statements:list[str]) -> list[str]`; the default
       offline synthesizer emits a simple template insight.
    5. `extract_recency` is corrected so the most-recently-accessed node gets
       the highest recency score (paper-faithful); upstream's index-based decay
       inverted this. Same exponential-decay curve, see that function's
       docstring.

The scoring algorithm itself (recency exponential decay + importance +
relevance cosine, min-max normalized, weighted sum, top-x) is UNCHANGED from
Stanford's retrieve.py `new_retrieve`.
"""

from __future__ import annotations

import datetime
import hashlib
import math
import re

# --------------------------------------------------------------------------- #
# Default offline injected callables (replace the LLM/embedding API calls).    #
# --------------------------------------------------------------------------- #

# A small lexicon of "poignant" cues -> bumps the importance score. This is a
# crude stand-in for the GPT poignancy prompt used in the paper; callers should
# inject a real importance_fn (e.g. an LLM or a trained scorer) in production.
_POIGNANT_CUES = {
    "love", "death", "die", "died", "breakup", "break-up", "divorce",
    "wedding", "married", "born", "birth", "fired", "hired", "promotion",
    "accident", "fight", "war", "win", "won", "lost", "loss", "accepted",
    "rejected", "graduate", "graduation", "betray", "danger", "emergency",
    "crash", "profit", "loss", "alert", "critical", "important", "urgent",
}


def default_importance_fn(text: str) -> int:
    """Deterministic offline poignancy score in [1, 10].

    Heuristic stand-in for Stanford's GPT poignancy prompt
    ("rate 1=mundane .. 10=poignant"). Score grows with the number of
    poignant cue words and (mildly) with statement length.
    """
    if not text:
        return 1
    tokens = re.findall(r"[a-zA-Z']+", text.lower())
    cue_hits = sum(1 for t in tokens if t in _POIGNANT_CUES)
    length_bonus = min(len(tokens) // 8, 2)  # 0..2
    score = 1 + cue_hits * 3 + length_bonus
    return max(1, min(10, score))


def default_embed_fn(text: str, dim: int = 64) -> list[float]:
    """Deterministic offline bag-of-hashed-words embedding (L2-normalized).

    Stand-in for an embedding API. Same words -> same vector; shared words ->
    higher cosine similarity. No network, fully reproducible.
    """
    vec = [0.0] * dim
    for tok in re.findall(r"[a-zA-Z']+", text.lower()):
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 7) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    else:
        vec[0] = 1.0  # avoid zero vector (cos_sim divide-by-zero)
    return vec


def default_synthesize_fn(statements: list[str]) -> list[str]:
    """Offline reflection synthesizer (stand-in for Stanford's GPT insight gen).

    Returns one templated higher-level insight summarizing the focal
    statements. Inject a real LLM-backed synthesizer for quality insights.
    """
    if not statements:
        return []
    head = "; ".join(s.strip() for s in statements[:3] if s.strip())
    return [f"Reflecting on recent experiences, a pattern emerges: {head}."]


# --------------------------------------------------------------------------- #
# ConceptNode -- verbatim structure from Stanford associative_memory.py        #
# --------------------------------------------------------------------------- #

class ConceptNode:
    def __init__(self,
                 node_id, node_count, type_count, node_type, depth,
                 created, expiration,
                 s, p, o,
                 description, embedding_key, poignancy, keywords, filling):
        self.node_id = node_id
        self.node_count = node_count
        self.type_count = type_count
        self.type = node_type  # thought / event / chat
        self.depth = depth

        self.created = created
        self.expiration = expiration
        self.last_accessed = self.created

        self.subject = s
        self.predicate = p
        self.object = o

        self.description = description
        self.embedding_key = embedding_key
        self.poignancy = poignancy
        self.keywords = keywords
        self.filling = filling

    def spo_summary(self):
        return (self.subject, self.predicate, self.object)

    def __repr__(self):
        return f"<ConceptNode {self.node_id} {self.type} '{self.description}'>"


# --------------------------------------------------------------------------- #
# Retrieval math -- verbatim from Stanford retrieve.py (cos_sim de-numpy'd).   #
# --------------------------------------------------------------------------- #

def cos_sim(a, b):
    """Cosine similarity between two 1-D vectors (pure-Python; was numpy)."""
    dot = sum(i * j for i, j in zip(a, b))
    na = math.sqrt(sum(i * i for i in a))
    nb = math.sqrt(sum(i * i for i in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def normalize_dict_floats(d, target_min, target_max):
    """Normalize a dict's float values into [target_min, target_max]."""
    if not d:
        return d
    min_val = min(val for val in d.values())
    max_val = max(val for val in d.values())
    range_val = max_val - min_val
    if range_val == 0:
        for key in d:
            d[key] = (target_max - target_min) / 2
    else:
        for key, val in d.items():
            d[key] = ((val - min_val) * (target_max - target_min)
                      / range_val + target_min)
    return d


def top_highest_x_values(d, x):
    """Return the top-x key/value pairs of d by value."""
    return dict(sorted(d.items(), key=lambda item: item[1], reverse=True)[:x])


def extract_recency(nodes, recency_decay):
    """Recency = exponential decay over how recently a node was accessed.

    EDIT (#5) vs. Stanford retrieve.py: the upstream code does
        recency_vals = [recency_decay ** i for i in range(1, len(nodes)+1)]
        recency_out[node_id] = recency_vals[count]
    with `nodes` sorted ASCENDING by last_accessed, which assigns the
    *largest* decay value (recency_decay**1) to the LEAST recently accessed
    node -- inverting the paper's intent ("higher score to objects recently
    accessed"). We keep the identical exponential-decay curve but assign
    recency_decay**1 to the MOST recent node, so newest -> highest recency,
    matching Section 4.1 of the paper and this project's GA goal.
    """
    n = len(nodes)
    recency_vals = [recency_decay ** i for i in range(1, n + 1)]
    recency_out = dict()
    for count, node in enumerate(nodes):  # nodes ascending by last_accessed
        recency_out[node.node_id] = recency_vals[n - 1 - count]
    return recency_out


def extract_importance(nodes):
    """Importance = node.poignancy."""
    importance_out = dict()
    for node in nodes:
        importance_out[node.node_id] = node.poignancy
    return importance_out


def extract_relevance(memory, nodes, focal_pt):
    """Relevance = cosine similarity of node embedding to focal-point embedding."""
    focal_embedding = memory.embed_fn(focal_pt)
    relevance_out = dict()
    for node in nodes:
        node_embedding = memory.embeddings[node.embedding_key]
        relevance_out[node.node_id] = cos_sim(node_embedding, focal_embedding)
    return relevance_out


# --------------------------------------------------------------------------- #
# AssociativeMemory == the "Memory Stream" (decoupled from persona/LLM).       #
# --------------------------------------------------------------------------- #

class AssociativeMemory:
    """Generative-Agents memory stream.

    Hyper-parameter defaults match Stanford scratch.py.
    """

    def __init__(self,
                 importance_fn=default_importance_fn,
                 embed_fn=default_embed_fn,
                 synthesize_fn=default_synthesize_fn,
                 recency_w: float = 1.0,
                 relevance_w: float = 1.0,
                 importance_w: float = 1.0,
                 recency_decay: float = 0.99,
                 importance_trigger_max: int = 150):
        # injected callables (offline defaults)
        self.importance_fn = importance_fn
        self.embed_fn = embed_fn
        self.synthesize_fn = synthesize_fn

        # retrieval / reflection hyper-parameters (Stanford scratch.py defaults)
        self.recency_w = recency_w
        self.relevance_w = relevance_w
        self.importance_w = importance_w
        self.recency_decay = recency_decay
        self.importance_trigger_max = importance_trigger_max
        self.importance_trigger_curr = importance_trigger_max
        self.importance_ele_n = 0

        # stores (verbatim from Stanford AssociativeMemory)
        self.id_to_node = dict()
        self.seq_event = []
        self.seq_thought = []
        self.seq_chat = []
        self.kw_to_event = dict()
        self.kw_to_thought = dict()
        self.kw_strength_event = dict()
        self.kw_strength_thought = dict()
        self.embeddings = dict()

    # ----- low-level node insertion (verbatim Stanford logic) -------------- #

    def add_event(self, created, expiration, s, p, o,
                  description, keywords, poignancy, embedding_pair, filling):
        node_count = len(self.id_to_node.keys()) + 1
        type_count = len(self.seq_event) + 1
        node_type = "event"
        node_id = f"node_{str(node_count)}"
        depth = 0

        if "(" in description:
            description = (" ".join(description.split()[:3])
                           + " " + description.split("(")[-1][:-1])

        node = ConceptNode(node_id, node_count, type_count, node_type, depth,
                           created, expiration, s, p, o,
                           description, embedding_pair[0],
                           poignancy, keywords, filling)

        self.seq_event[0:0] = [node]
        keywords = [i.lower() for i in keywords]
        for kw in keywords:
            if kw in self.kw_to_event:
                self.kw_to_event[kw][0:0] = [node]
            else:
                self.kw_to_event[kw] = [node]
        self.id_to_node[node_id] = node

        if f"{p} {o}" != "is idle":
            for kw in keywords:
                self.kw_strength_event[kw] = self.kw_strength_event.get(kw, 0) + 1

        self.embeddings[embedding_pair[0]] = embedding_pair[1]
        return node

    def add_thought(self, created, expiration, s, p, o,
                    description, keywords, poignancy, embedding_pair, filling):
        node_count = len(self.id_to_node.keys()) + 1
        type_count = len(self.seq_thought) + 1
        node_type = "thought"
        node_id = f"node_{str(node_count)}"
        depth = 1
        try:
            if filling:
                depth += max([self.id_to_node[i].depth for i in filling])
        except Exception:
            pass

        node = ConceptNode(node_id, node_count, type_count, node_type, depth,
                           created, expiration, s, p, o,
                           description, embedding_pair[0],
                           poignancy, keywords, filling)

        self.seq_thought[0:0] = [node]
        keywords = [i.lower() for i in keywords]
        for kw in keywords:
            if kw in self.kw_to_thought:
                self.kw_to_thought[kw][0:0] = [node]
            else:
                self.kw_to_thought[kw] = [node]
        self.id_to_node[node_id] = node

        if f"{p} {o}" != "is idle":
            for kw in keywords:
                self.kw_strength_thought[kw] = self.kw_strength_thought.get(kw, 0) + 1

        self.embeddings[embedding_pair[0]] = embedding_pair[1]
        return node

    # ----- convenience API (injected importance + embedding) --------------- #

    def add_observation(self, description, created=None, kind="event",
                        s=None, p=None, o=None, keywords=None,
                        poignancy=None, expiration=None, filling=None):
        """Add an observation to the stream.

        Computes poignancy via importance_fn and the embedding via embed_fn
        unless explicitly provided. `kind` is "event" or "thought".
        Returns the created ConceptNode.
        """
        created = created or datetime.datetime.now()
        if poignancy is None:
            poignancy = self.importance_fn(description)
        if keywords is None:
            keywords = set(re.findall(r"[a-zA-Z']+", description.lower()))
        if s is None:
            s, p, o = "observer", "observed", description
        embedding_pair = (description, self.embed_fn(description))
        filling = filling or []

        # accumulate importance toward the reflection trigger (Stanford behavior)
        self.importance_trigger_curr -= poignancy
        self.importance_ele_n += 1

        if kind == "thought":
            return self.add_thought(created, expiration, s, p, o, description,
                                   keywords, poignancy, embedding_pair, filling)
        return self.add_event(created, expiration, s, p, o, description,
                             keywords, poignancy, embedding_pair, filling)

    # ----- retrieval (Stanford new_retrieve, decoupled) -------------------- #

    def retrieve(self, focal_points, n_count=30, gw=(0.5, 3, 2),
                 update_last_accessed=True, curr_time=None):
        """Retrieve the most salient nodes for each focal point.

        Salience = recency_w * recency * gw[0]
                 + relevance_w * relevance * gw[1]
                 + importance_w * importance * gw[2]
        (recency / relevance / importance each min-max normalized to [0,1]).

        Args:
            focal_points: str or list[str] -- current situation / query.
            n_count: max nodes to return per focal point.
            gw: global weight triple (recency, relevance, importance);
                Stanford default (0.5, 3, 2).
        Returns:
            dict {focal_point: [ConceptNode, ...]} ranked high->low.
        """
        if isinstance(focal_points, str):
            focal_points = [focal_points]
        curr_time = curr_time or datetime.datetime.now()

        retrieved = dict()
        for focal_pt in focal_points:
            nodes = [[i.last_accessed, i]
                     for i in self.seq_event + self.seq_thought
                     if "idle" not in i.embedding_key]
            nodes = sorted(nodes, key=lambda x: x[0])
            nodes = [i for _, i in nodes]
            if not nodes:
                retrieved[focal_pt] = []
                continue

            recency_out = extract_recency(nodes, self.recency_decay)
            recency_out = normalize_dict_floats(recency_out, 0, 1)
            importance_out = extract_importance(nodes)
            importance_out = normalize_dict_floats(importance_out, 0, 1)
            relevance_out = extract_relevance(self, nodes, focal_pt)
            relevance_out = normalize_dict_floats(relevance_out, 0, 1)

            master_out = dict()
            for key in recency_out.keys():
                master_out[key] = (self.recency_w * recency_out[key] * gw[0]
                                   + self.relevance_w * relevance_out[key] * gw[1]
                                   + self.importance_w * importance_out[key] * gw[2])

            master_out = top_highest_x_values(master_out, n_count)
            master_nodes = [self.id_to_node[key] for key in master_out.keys()]

            if update_last_accessed:
                for n in master_nodes:
                    n.last_accessed = curr_time

            retrieved[focal_pt] = master_nodes
        return retrieved

    # ----- reflection (Stanford reflect.py, decoupled) --------------------- #

    def reflection_trigger(self):
        """True when accumulated importance has crossed the threshold."""
        return (self.importance_trigger_curr <= 0
                and (self.seq_event + self.seq_thought) != [])

    def reset_reflection_counter(self):
        self.importance_trigger_curr = self.importance_trigger_max
        self.importance_ele_n = 0

    def generate_focal_points(self, n=3):
        """Focal points = the most recent importance_ele_n observations."""
        nodes = [[i.last_accessed, i]
                 for i in self.seq_event + self.seq_thought
                 if "idle" not in i.embedding_key]
        nodes = sorted(nodes, key=lambda x: x[0])
        nodes = [i for _, i in nodes]
        statements = [n.embedding_key for n in nodes[-self.importance_ele_n:]] \
            if self.importance_ele_n else [n.embedding_key for n in nodes]
        # Stanford asks an LLM for n focal questions; offline we reuse the
        # statements themselves as focal points (capped at n).
        return statements[-n:] if statements else []

    def run_reflect(self, n_insights=3, curr_time=None):
        """Synthesize higher-level insight thoughts and store them as nodes.

        Returns the list of newly created insight ConceptNodes.
        """
        curr_time = curr_time or datetime.datetime.now()
        focal_points = self.generate_focal_points(3)
        retrieved = self.retrieve(focal_points, n_count=n_insights,
                                  curr_time=curr_time)

        created_nodes = []
        for focal_pt, nodes in retrieved.items():
            statements = [n.description for n in nodes]
            insights = self.synthesize_fn(statements)
            for thought in insights:
                expiration = curr_time + datetime.timedelta(days=30)
                evidence = [n.node_id for n in nodes]
                node = self.add_observation(
                    thought, created=curr_time, kind="thought",
                    expiration=expiration, filling=evidence)
                created_nodes.append(node)
        return created_nodes

    def reflect(self, curr_time=None):
        """Run reflection if the importance trigger fires; reset the counter.

        Returns the list of new insight nodes (empty if not triggered).
        """
        new_nodes = []
        if self.reflection_trigger():
            new_nodes = self.run_reflect(curr_time=curr_time)
            self.reset_reflection_counter()
        return new_nodes


# Alias matching the paper's terminology.
MemoryStream = AssociativeMemory
