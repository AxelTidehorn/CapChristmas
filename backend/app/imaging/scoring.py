"""Deterministic V1 distance:
D_i = Σ_k w_k · MSE(G_σk(I_i), G_σk(M)), lowest D wins, ties broken by drawing id."""
import cv2
import numpy as np

from .. import config as C


def _blur(x: np.ndarray, sigma: float) -> np.ndarray:
    return cv2.GaussianBlur(x.astype(np.float64), (0, 0), sigma, borderType=cv2.BORDER_CONSTANT)


class Scorer:
    def __init__(self, mean: np.ndarray, sigmas=None, weights=None):
        cfg = C.scoring_config()
        self.sigmas = list(sigmas or cfg["sigmas_px"])
        self.weights = list(weights or cfg["weights"])
        self.mean_blurred = [_blur(mean, s) for s in self.sigmas]

    def components(self, ink: np.ndarray) -> list[float]:
        return [float(np.mean((_blur(ink, s) - mb) ** 2)) for s, mb in zip(self.sigmas, self.mean_blurred)]

    def distance(self, ink: np.ndarray) -> tuple[float, list[float]]:
        comps = self.components(ink)
        return float(sum(w * c for w, c in zip(self.weights, comps))), comps


def rank(distances: dict[str, float]) -> list[dict]:
    """[{id, rank, distance, tied}] sorted by (distance, id). Equal ranks only for exactly equal floats."""
    order = sorted(distances, key=lambda d: (distances[d], d))
    out, prev = [], None
    for pos, did in enumerate(order, 1):
        dist = distances[did]
        tied = prev is not None and dist == prev["distance"]
        if tied:
            prev["tied"] = True
        out.append({"id": did, "position": pos, "rank": prev["rank"] if tied else pos,
                    "distance": dist, "tied": tied})
        prev = out[-1]
    return out
