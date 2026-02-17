"""Markov removal-effect MTA: transition matrix and removal-effect credit. Fallback when insufficient data."""
from typing import Dict, List, Tuple

import numpy as np


def build_transition_matrix(
    sequences: List[List[str]],
    channels: List[str],
) -> np.ndarray:
    """
    Build transition count matrix (row = from, col = to); then normalize to probabilities.
    sequences: list of touchpoint sequences (e.g. ["meta", "google", "meta"]).
    channels: ordered list of channel labels (index i corresponds to row/col i).
    """
    n = len(channels)
    idx = {c: i for i, c in enumerate(channels)}
    mat = np.zeros((n + 1, n + 1))  # +1 for start/end
    start_idx, end_idx = n, n
    for seq in sequences:
        if not seq:
            continue
        prev = start_idx
        for ch in seq:
            i = idx.get(ch, end_idx)
            if i == end_idx:
                continue
            mat[prev, i] += 1
            prev = i
        mat[prev, end_idx] += 1
    row_sums = mat.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    return (mat / row_sums).astype(float)


def removal_effect(
    transition_matrix: np.ndarray,
    channel_index: int,
    end_index: int,
) -> float:
    """
    Removal effect for channel at channel_index: probability of reaching end
    when we remove that channel (set its row/col to 0 and renormalize).
    Returns 1 - P(reach end without channel) as the contribution share.
    """
    n = transition_matrix.shape[0] - 1
    if n <= 0 or channel_index < 0 or channel_index >= n:
        return 0.0
    P = transition_matrix.copy()
    P[channel_index, :] = 0
    P[:, channel_index] = 0
    row_sums = P.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    P = P / row_sums
    start_idx = n
    probs = np.zeros(n + 1)
    probs[start_idx] = 1.0
    for _ in range(2 * (n + 1)):
        next_p = probs @ P
        if np.allclose(next_p, probs):
            break
        probs = next_p
    return float(1.0 - probs[end_index]) if end_index < len(probs) else 0.0


def markov_credits(
    sequences: List[List[str]],
    channels: List[str],
    min_sequences: int = 10,
) -> Dict[str, float] | None:
    """
    Compute removal-effect credit per channel. If len(sequences) < min_sequences, return None (fallback to fractional).
    """
    if len(sequences) < min_sequences:
        return None
    P = build_transition_matrix(sequences, channels)
    n = len(channels)
    end_idx = n
    effects = []
    for i in range(n):
        e = removal_effect(P, i, end_idx)
        effects.append(e)
    total = float(sum(effects))
    if total <= 0:
        return {ch: 1.0 / len(channels) for ch in channels}
    return {ch: float(effects[i] / total) for i, ch in enumerate(channels)}
