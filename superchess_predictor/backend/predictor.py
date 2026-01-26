"""Probability computation utilities."""
from __future__ import annotations

from typing import Dict, List

import numpy as np


def compute_move_probabilities(
    tagged_moves: List[dict],
    player_distributions: Dict[str, Dict[str, float]],
) -> List[Dict[str, float]]:
    if not tagged_moves:
        return []

    all_tags = sorted({tag for dist in player_distributions.values() for tag in dist})
    if not all_tags:
        return [
            {player: 1.0 / len(player_distributions) for player in player_distributions}
            for _ in tagged_moves
        ]

    player_vectors = {
        player: np.array([dist.get(tag, 0.0) for tag in all_tags], dtype=float)
        for player, dist in player_distributions.items()
    }

    for vec in player_vectors.values():
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm

    probabilities: List[Dict[str, float]] = []
    player_names = list(player_vectors.keys())

    for move in tagged_moves:
        tags = set(move.get("tags") or [])
        move_vec = np.array([1.0 if tag in tags else 0.0 for tag in all_tags], dtype=float)
        norm = np.linalg.norm(move_vec)
        if norm > 0:
            move_vec /= norm

        scores = []
        for player in player_names:
            player_vec = player_vectors[player]
            score = float(np.dot(move_vec, player_vec)) if norm > 0 else 0.0
            scores.append(score)

        scores_arr = np.array(scores, dtype=float)
        if np.all(scores_arr == 0):
            probs = np.full(len(player_names), 1.0 / len(player_names))
        else:
            exp_scores = np.exp(scores_arr - np.max(scores_arr))
            probs = exp_scores / exp_scores.sum()

        probabilities.append({player: float(prob) for player, prob in zip(player_names, probs)})

    return probabilities
