"""Module C — Score normalization formulas.

Each sub-score is computed as a weighted mean of normalized metric values.
Normalization maps raw metric values to a 0-100 scale using defined
ideal/worst thresholds per metric.

Modify the METRIC_RANGES and WEIGHTS dicts below to tune scoring.
"""

from typing import Dict, Optional

# --- Normalization ranges ---
# (metric_name, direction, ideal_value, worst_value)
# direction: "lower_is_better" or "higher_is_better"
METRIC_RANGES: Dict[str, dict] = {
    # B1: Delivery
    "lead_time": {
        "direction": "lower_is_better",
        "ideal": 2.0,       # 2 hours = perfect
        "worst": 72.0,      # 72 hours = score 0
        "unit": "hours",
    },
    "deployment_frequency": {
        "direction": "higher_is_better",
        "ideal": 10.0,      # 10 deploys/week = perfect
        "worst": 0.0,       # 0 deploys/week = score 0
        "unit": "deploys/week",
    },
    "cycle_time": {
        "direction": "lower_is_better",
        "ideal": 8.0,       # 8 hours = perfect
        "worst": 168.0,     # 1 week = score 0
        "unit": "hours",
    },
    # B2: Quality
    "change_failure_rate": {
        "direction": "lower_is_better",
        "ideal": 0.0,       # 0% = perfect
        "worst": 50.0,      # 50% = score 0
        "unit": "percentage",
    },
    "mttr": {
        "direction": "lower_is_better",
        "ideal": 0.5,       # 30 min = perfect
        "worst": 24.0,      # 24 hours = score 0
        "unit": "hours",
    },
    "defect_density": {
        "direction": "lower_is_better",
        "ideal": 0.0,       # 0 defects/kloc = perfect
        "worst": 50.0,      # 50 defects/kloc = score 0
        "unit": "defects/kloc",
    },
    "test_coverage": {
        "direction": "higher_is_better",
        "ideal": 95.0,      # 95% = perfect
        "worst": 0.0,       # 0% = score 0
        "unit": "percentage",
    },
    "rework_ratio": {
        "direction": "lower_is_better",
        "ideal": 0.0,       # 0% = perfect
        "worst": 40.0,      # 40% = score 0
        "unit": "percentage",
    },
    # B3: Team Experience
    "code_review_turnaround": {
        "direction": "lower_is_better",
        "ideal": 2.0,       # 2 hours = perfect
        "worst": 48.0,      # 48 hours = score 0
        "unit": "hours",
    },
    "wip_count": {
        "direction": "lower_is_better",
        "ideal": 1.0,       # 1 task = perfect
        "worst": 10.0,      # 10 tasks = score 0
        "unit": "count",
    },
    "dxi": {
        "direction": "higher_is_better",
        "ideal": 100.0,     # 100 = perfect
        "worst": 0.0,       # 0 = score 0
        "unit": "score",
    },
    # B4: Business
    "dollar_productivity": {
        "direction": "higher_is_better",
        "ideal": 100000.0,  # $100K = perfect
        "worst": 0.0,       # $0 = score 0
        "unit": "dollars",
    },
}

# --- Sub-score weights (within each category) ---
# Each maps metric_name -> relative weight. They're normalized internally.
CATEGORY_METRIC_WEIGHTS: Dict[str, Dict[str, float]] = {
    "delivery": {
        "lead_time": 0.35,
        "deployment_frequency": 0.35,
        "cycle_time": 0.30,
    },
    "quality": {
        "change_failure_rate": 0.25,
        "mttr": 0.25,
        "defect_density": 0.15,
        "test_coverage": 0.20,
        "rework_ratio": 0.15,
    },
    "team_exp": {
        "code_review_turnaround": 0.35,
        "wip_count": 0.25,
        "dxi": 0.40,
    },
    "business": {
        "dollar_productivity": 1.0,
    },
}

# --- Overall score weights (FRD spec) ---
OVERALL_WEIGHTS = {
    "delivery": 0.25,
    "quality": 0.25,
    "team_exp": 0.15,
    "business": 0.35,
}


def normalize_metric(metric_name: str, raw_value: float) -> float:
    """Normalize a raw metric value to 0-100 scale.

    Returns a score between 0 and 100.
    """
    config = METRIC_RANGES.get(metric_name)
    if not config:
        return 0.0

    ideal = config["ideal"]
    worst = config["worst"]

    if config["direction"] == "lower_is_better":
        # Lower raw value = higher score
        if raw_value <= ideal:
            return 100.0
        if raw_value >= worst:
            return 0.0
        return round((worst - raw_value) / (worst - ideal) * 100, 2)
    else:
        # Higher raw value = higher score
        if raw_value >= ideal:
            return 100.0
        if raw_value <= worst:
            return 0.0
        return round((raw_value - worst) / (ideal - worst) * 100, 2)


def compute_sub_score(
    category: str, metric_values: Dict[str, float]
) -> tuple:
    """Compute a weighted sub-score (0-100) for a category.

    Args:
        category: One of "delivery", "quality", "team_exp", "business"
        metric_values: Dict of {metric_name: raw_value}

    Returns:
        (score, breakdown_dict) where breakdown shows per-metric normalized scores
    """
    weights = CATEGORY_METRIC_WEIGHTS.get(category, {})
    if not weights:
        return 0.0, {}

    total_weight = 0.0
    weighted_sum = 0.0
    breakdown = {}

    for metric_name, weight in weights.items():
        raw_value = metric_values.get(metric_name)
        if raw_value is None:
            continue

        normalized = normalize_metric(metric_name, raw_value)
        weighted_sum += normalized * weight
        total_weight += weight
        breakdown[metric_name] = {
            "raw_value": raw_value,
            "normalized_score": normalized,
            "weight": weight,
        }

    score = round(weighted_sum / total_weight, 2) if total_weight > 0 else 0.0
    return score, breakdown


def compute_overall_score(sub_scores: Dict[str, float]) -> float:
    """Compute the overall weighted score from sub-scores.

    Formula from FRD:
    OverallScore = 0.25*Delivery + 0.25*Quality + 0.15*TeamExp + 0.35*Business
    """
    total = 0.0
    for category, weight in OVERALL_WEIGHTS.items():
        total += sub_scores.get(category, 0.0) * weight
    return round(total, 2)
