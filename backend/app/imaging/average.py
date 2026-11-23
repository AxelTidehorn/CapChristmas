"""The real pixel mean M = (1/N) Σ I_i, plus a separate display-only enhancement."""
from collections.abc import Iterable

import numpy as np


def mean_image(inks: Iterable[np.ndarray]) -> np.ndarray:
    total, n = None, 0
    for ink in inks:  # streaming: never holds more than one ink map besides the sum
        total = ink.astype(np.float64) if total is None else total + ink
        n += 1
    if n == 0:
        raise ValueError("Inga godkända teckningar att medelvärdesbilda.")
    return total / n


def display_enhance(mean: np.ndarray) -> np.ndarray:
    """Contrast stretch for the projector. NEVER used for scoring."""
    hi = float(np.percentile(mean, 99.5))
    if hi <= 1e-9:
        return np.zeros_like(mean)
    return np.clip(mean / hi, 0, 1) ** 0.7
