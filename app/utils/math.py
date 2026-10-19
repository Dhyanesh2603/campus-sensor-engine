from collections.abc import Sequence


def compute_aggregation(values: Sequence[float], aggregation: str) -> float | None:
    if not values:
        return None

    agg = aggregation.upper()
    if agg == "COUNT":
        return float(len(values))
    elif agg == "AVG":
        return sum(values) / len(values)
    elif agg == "MIN":
        return min(values)
    elif agg == "MAX":
        return max(values)
    return None
