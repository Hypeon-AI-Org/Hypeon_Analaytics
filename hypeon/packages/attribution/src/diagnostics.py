"""
Attribution diagnostics: path frequency, removal effect, bootstrap CI, lag distribution,
window sensitivity, and confidence score. All outputs deterministic; confidence clamped [0, 1].
"""
import math
import random
from collections import Counter
from typing import Dict, List, Optional, Any

from packages.attribution.src.markov import (
    build_transition_matrix,
    removal_effect,
    markov_credits,
)


def compute_path_frequency(sequences: List[List[str]]) -> Dict[str, int]:
    """
    Count path patterns from touchpoint sequences.
    Path format: "ch1>ch2>ch3" for sequence [ch1, ch2, ch3].
    Returns dict mapping path string -> count.
    """
    counter: Counter = Counter()
    for seq in sequences:
        if not seq:
            continue
        path = ">".join(seq)
        counter[path] += 1
    return dict(counter)


def compute_removal_effect_table(
    sequences: List[List[str]],
    channels: List[str],
) -> Dict[str, float]:
    """
    Build channel -> removal-effect table using Markov transition matrix.
    Uses build_transition_matrix and removal_effect from markov module.
    """
    if len(sequences) < 2 or not channels:
        return {ch: 0.0 for ch in channels}
    P = build_transition_matrix(sequences, channels)
    n = len(channels)
    end_idx = n
    effects = []
    for i in range(n):
        e = removal_effect(P, i, end_idx)
        effects.append(e)
    total = sum(effects) or 1.0
    return {ch: effects[i] / total for i, ch in enumerate(channels)}


def bootstrap_channel_contributions(
    sequences: List[List[str]],
    channels: List[str],
    n_boot: int = 500,
    min_sequences: int = 5,
    seed: Optional[int] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Bootstrap allocation samples to get per-channel CIs (low, mean, high).
    If sample size is small, reduce n_boot or return empty CIs. Never crash.
    """
    if seed is not None:
        random.seed(seed)
    n_seq = len(sequences)
    if n_seq < min_sequences or not channels:
        return {
            ch: {"low": 0.0, "mean": 0.0, "high": 0.0, "variance": 0.0}
            for ch in channels
        }
    n_boot = min(n_boot, max(50, n_seq * 2))
    boot_credits: List[Dict[str, float]] = []
    for _ in range(n_boot):
        sample = random.choices(sequences, k=len(sequences))
        credits = markov_credits(sample, channels, min_sequences=2)
        if credits is None:
            total = sum(channels)
            credits = {ch: 1.0 / len(channels) for ch in channels} if channels else {}
        boot_credits.append(credits)
    result: Dict[str, Dict[str, float]] = {}
    for ch in channels:
        values = [c.get(ch, 0.0) for c in boot_credits]
        mean_val = sum(values) / len(values) if values else 0.0
        variance = sum((x - mean_val) ** 2 for x in values) / len(values) if values else 0.0
        sorted_vals = sorted(values)
        n_v = len(sorted_vals)
        low = sorted_vals[int(0.025 * n_v)] if n_v else 0.0
        high = sorted_vals[int(0.975 * n_v)] if n_v else 0.0
        result[ch] = {"low": low, "mean": mean_val, "high": high, "variance": variance}
    return result


def compute_lag_distribution(sequences: List[List[str]]) -> Dict[str, Any]:
    """
    Distribution of touch position (first-touch, last-touch, etc.).
    Returns position index (0=first, -1=last) counts and shares.
    """
    if not sequences:
        return {"position_counts": {}, "position_shares": {}, "num_paths": 0}
    first_touch = 0
    last_touch = 0
    position_counts: Dict[int, int] = {}
    for seq in sequences:
        if not seq:
            continue
        first_touch += 1
        last_touch += 1
        for i, _ in enumerate(seq):
            position_counts[i] = position_counts.get(i, 0) + 1
    total_positions = sum(position_counts.values()) or 1
    position_shares = {k: v / total_positions for k, v in position_counts.items()}
    return {
        "position_counts": position_counts,
        "position_shares": position_shares,
        "num_paths": len([s for s in sequences if s]),
        "first_touch_count": first_touch,
        "last_touch_count": last_touch,
    }


def window_sensitivity_analysis(
    sequences: List[List[str]],
    channels: List[str],
    windows: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Run removal-effect attribution for different window lengths (subsequence length).
    Returns per-channel allocation for each window and sensitivity summary.
    """
    if windows is None:
        windows = [7, 14, 30]
    if not sequences or not channels:
        return {"by_window": {}, "channels": channels, "windows": windows}
    by_window: Dict[int, Dict[str, float]] = {}
    for w in windows:
        truncated = [seq[:w] for seq in sequences if seq]
        if len(truncated) < 2:
            by_window[w] = {ch: 1.0 / len(channels) for ch in channels}
            continue
        credits = markov_credits(truncated, channels, min_sequences=2)
        if credits is None:
            by_window[w] = {ch: 1.0 / len(channels) for ch in channels}
        else:
            by_window[w] = credits
    return {"by_window": by_window, "channels": channels, "windows": windows}


def _confidence_score(
    path_frequency: Dict[str, int],
    bootstrap_ci: Dict[str, Dict[str, float]],
    conversion_density_score: float = 1.0,
) -> float:
    """
    confidence = (1 - avg(channel_bootstrap_variance)) * min(1, log(num_paths)/10) * conversion_density_score
    Clamped to [0, 1].
    """
    num_paths = sum(path_frequency.values()) or 0
    if num_paths == 0:
        return 0.0
    variances = [b["variance"] for b in bootstrap_ci.values() if "variance" in b]
    avg_var = sum(variances) / len(variances) if variances else 0.0
    term1 = 1.0 - avg_var
    term2 = min(1.0, math.log1p(num_paths) / 10.0)
    term3 = max(0.0, min(1.0, conversion_density_score))
    score = term1 * term2 * term3
    return max(0.0, min(1.0, score))


def run_diagnostics(
    sequences: List[List[str]],
    channels: Optional[List[str]] = None,
    n_boot: int = 500,
    windows: Optional[List[int]] = None,
    conversion_density_score: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Run all diagnostics and return structured object with path_frequency, removal_effect,
    bootstrap_ci, lag_distribution, window_sensitivity, confidence_score.
    confidence_score is clamped to [0, 1].
    """
    if channels is None:
        all_ch = set()
        for seq in sequences:
            all_ch.update(seq)
        channels = sorted(all_ch) if all_ch else ["meta", "google"]
    path_freq = compute_path_frequency(sequences)
    removal = compute_removal_effect_table(sequences, channels)
    bootstrap_ci = bootstrap_channel_contributions(sequences, channels, n_boot=n_boot)
    lag_dist = compute_lag_distribution(sequences)
    window_sens = window_sensitivity_analysis(sequences, channels, windows=windows)
    num_paths = sum(path_freq.values()) or 0
    if conversion_density_score is None:
        conversion_density_score = 1.0 if num_paths > 0 else 0.0
    confidence = _confidence_score(path_freq, bootstrap_ci, conversion_density_score)
    return {
        "path_frequency": path_freq,
        "removal_effect": removal,
        "bootstrap_ci": bootstrap_ci,
        "lag_distribution": lag_dist,
        "window_sensitivity": window_sens,
        "confidence_score": confidence,
    }
