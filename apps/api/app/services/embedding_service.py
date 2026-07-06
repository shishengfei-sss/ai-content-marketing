"""本地 deterministic embedding（零外网，与 LM5 / C4 共用）。"""

from __future__ import annotations

import hashlib
import json
import math
import re

EMBED_DIM = 64


def embed_text(text: str, *, dim: int = EMBED_DIM) -> list[float]:
    vec = [0.0] * dim
    t = text.lower().strip()
    if not t:
        return vec
    for i in range(max(1, len(t) - 2)):
        gram = t[i : i + 3]
        idx = int(hashlib.md5(gram.encode("utf-8")).hexdigest(), 16) % dim
        vec[idx] += 1.0
    for token in re.split(r"[\s，。、；：！？]+", t):
        if len(token) >= 2:
            idx = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % dim
            vec[idx] += 1.5
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def embedding_to_json(vec: list[float]) -> str:
    return json.dumps(vec, separators=(",", ":"))


def embedding_from_json(raw: str | None) -> list[float] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None
    return [float(x) for x in data]


def vector_to_pg_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"
