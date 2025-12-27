"""
Transaction threshold validation tools.

Implements regulatory reporting thresholds for AML compliance.
These thresholds trigger automatic reporting requirements.
"""

import json
from typing import Optional


# Regulatory thresholds by currency (simplified)
REPORTING_THRESHOLDS = {
    "USD": 10000,  # US Bank Secrecy Act
    "EUR": 10000,  # EU 4th AML Directive
    "GBP": 10000,  # UK Money Laundering Regulations
    "CHF": 15000,  # Swiss AMLA
    "JPY": 2000000,  # Japan (~$13,500)
    "DEFAULT": 10000,
}

# Structuring detection - multiple transactions just under threshold
STRUCTURING_THRESHOLD_PERCENT = 0.9  # Transactions at 90%+ of threshold are suspicious


def validate_amount_threshold(
    amount: float,
    currency: str = "USD",
    transaction_count_24h: Optional[int] = None,
) -> str:
    """
    Validates transaction amount against regulatory reporting thresholds.
    
    Detects:
    - Threshold breaches requiring CTR (Currency Transaction Report)
    - Potential structuring (splitting transactions to avoid reporting)
    
    Args:
        amount: Transaction amount
        currency: Currency code (USD, EUR, etc.)
        transaction_count_24h: Optional count of transactions in last 24h
        
    Returns:
        JSON string with threshold validation result
    """
    currency = currency.upper()
    threshold = REPORTING_THRESHOLDS.get(currency, REPORTING_THRESHOLDS["DEFAULT"])
    
    result = {
        "amount": amount,
        "currency": currency,
        "threshold": threshold,
        "threshold_breached": False,
        "structuring_suspected": False,
        "flags": [],
        "recommendation": "PROCEED",
    }
    
    # Check if amount exceeds threshold
    if amount >= threshold:
        result["threshold_breached"] = True
        result["flags"].append(f"EXCEEDS_{currency}_THRESHOLD")
        result["recommendation"] = "FILE_CTR"
        result["report_required"] = "Currency Transaction Report (CTR)"
    
    # Check for potential structuring (amount just under threshold)
    structuring_limit = threshold * STRUCTURING_THRESHOLD_PERCENT
    if structuring_limit <= amount < threshold:
        result["structuring_suspected"] = True
        result["flags"].append("POTENTIAL_STRUCTURING")
        result["recommendation"] = "MANUAL_REVIEW"
        result["structuring_analysis"] = {
            "amount_percent_of_threshold": round((amount / threshold) * 100, 1),
            "suspicious_reason": "Transaction amount suspiciously close to reporting threshold",
        }
    
    # Check for multiple transactions (if provided)
    if transaction_count_24h is not None and transaction_count_24h > 3:
        result["flags"].append("MULTIPLE_TRANSACTIONS_24H")
        if amount * transaction_count_24h >= threshold:
            result["structuring_suspected"] = True
            result["flags"].append("AGGREGATE_EXCEEDS_THRESHOLD")
            result["recommendation"] = "FILE_SAR"
            result["aggregate_analysis"] = {
                "transaction_count": transaction_count_24h,
                "estimated_aggregate": amount * transaction_count_24h,
            }
    
    return json.dumps(result)

