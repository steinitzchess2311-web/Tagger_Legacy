"""Compute move likelihood based on player summaries."""
from __future__ import annotations

from typing import Dict, List

import numpy as np


def compute_move_probability(
    tagged_moves: List[dict],
    player_distribution: Dict[str, float],
) -> np.ndarray:
    """Return probabilities for each move based on cosine similarity."""
    if not tagged_moves:
        return np.array([])

    all_tags = sorted(player_distribution.keys())
    player_vec = np.array([player_distribution.get(tag, 0.0) for tag in all_tags], dtype=float)

    if np.linalg.norm(player_vec) == 0:
        return np.full(len(tagged_moves), 1.0 / len(tagged_moves))

    scores: List[float] = []
    player_norm = np.linalg.norm(player_vec)

    for move in tagged_moves:
        tags = set(move.get("tags") or [])
        vec = np.array([1.0 if tag in tags else 0.0 for tag in all_tags], dtype=float)
        norm = np.linalg.norm(vec)
        if norm == 0:
            scores.append(0.0)
            continue
        sim = float(np.dot(vec, player_vec) / (norm * player_norm))
        scores.append(sim)

    scores_arr = np.array(scores, dtype=float)
    if np.all(scores_arr == 0):
        return np.full(len(tagged_moves), 1.0 / len(tagged_moves))

    exp_scores = np.exp(scores_arr - np.max(scores_arr))
    probs = exp_scores / exp_scores.sum()
    return probs

