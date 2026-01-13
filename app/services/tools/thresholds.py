"""Transaction threshold validation."""
import json

THRESHOLDS = {"USD": 10000, "EUR": 10000, "DEFAULT": 10000}

def validate_amount_threshold(amount: float, currency: str = "USD") -> str:
    threshold = THRESHOLDS.get(currency.upper(), THRESHOLDS["DEFAULT"])
    breached = amount >= threshold
    structuring = threshold * 0.9 <= amount < threshold
    return json.dumps({
        "amount": amount,
        "threshold": threshold,
        "threshold_breached": breached,
        "structuring_suspected": structuring,
        "recommendation": "FILE_CTR" if breached else ("MANUAL_REVIEW" if structuring else "PROCEED"),
    })