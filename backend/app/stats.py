"""Summary statistics for one control."""
import math


def summarize(values: list[float], target_mean: float, target_sd: float) -> dict:
    """Observed mean, SD, CV%, and bias against the target.

    Uses the sample SD (n - 1), the convention for QC data.
    """
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": None, "sd": None, "cv_percent": None, "bias_percent": None}
    mean = sum(values) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1)) if n > 1 else 0.0
    return {
        "n": n,
        "mean": round(mean, 4),
        "sd": round(sd, 4),
        "cv_percent": round(sd / mean * 100, 2) if mean else None,
        "bias_percent": round((mean - target_mean) / target_mean * 100, 2) if target_mean else None,
        "target_mean": target_mean,
        "target_sd": target_sd,
    }
