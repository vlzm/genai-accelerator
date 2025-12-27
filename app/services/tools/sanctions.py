"""
Sanctions and PEP checking tools.

These are MOCK implementations for the interview demo.
In production, these would call real APIs like:
- OFAC (US Treasury)
- EU Sanctions List
- UN Security Council Consolidated List
- World-Check (Refinitiv)

The mock approach demonstrates the architecture without
requiring external API access during the interview.
"""

import json
from typing import Any


# Mock sanctions database (in production: real API or database)
SANCTIONS_LIST = {
    # Format: "name": {"list": "source", "reason": "description", "severity": "level"}
    "ahmed ivanov": {
        "list": "OFAC_SDN",
        "reason": "Terrorist financing",
        "severity": "CRITICAL",
        "added_date": "2023-01-15",
    },
    "shell corp ltd": {
        "list": "EU_SANCTIONS",
        "reason": "Money laundering front company",
        "severity": "CRITICAL",
        "added_date": "2022-08-20",
    },
    "ivan petrov": {
        "list": "UN_CONSOLIDATED",
        "reason": "Arms trafficking",
        "severity": "HIGH",
        "added_date": "2021-03-10",
    },
    "dark holdings llc": {
        "list": "OFAC_SDN",
        "reason": "Sanctions evasion",
        "severity": "CRITICAL",
        "added_date": "2024-02-01",
    },
    "maria gonzalez": {
        "list": "INTERPOL_RED",
        "reason": "Financial fraud",
        "severity": "HIGH",
        "added_date": "2023-11-05",
    },
}

# Mock PEP database (Politically Exposed Persons)
PEP_LIST = {
    "john smith": {
        "position": "Former Minister of Finance",
        "country": "Countryland",
        "risk_level": "MEDIUM",
        "active": False,
    },
    "elena volkova": {
        "position": "Current Deputy Governor",
        "country": "Regionstan",
        "risk_level": "HIGH",
        "active": True,
    },
    "carlos rodriguez": {
        "position": "Former Central Bank Director",
        "country": "Tropicalia",
        "risk_level": "MEDIUM",
        "active": False,
    },
}


def check_sanctions_list(entity_name: str) -> str:
    """
    Checks if a person or company is on global sanctions lists.
    
    This is a MOCK implementation for demo purposes.
    In production, this would query real sanctions databases.
    
    Args:
        entity_name: Full name of the person or company to check
        
    Returns:
        JSON string with sanctions check result
    """
    # Normalize name for lookup
    normalized_name = entity_name.lower().strip()
    
    # Check against mock database
    if normalized_name in SANCTIONS_LIST:
        match = SANCTIONS_LIST[normalized_name]
        return json.dumps({
            "is_sanctioned": True,
            "entity_name": entity_name,
            "sanctions_list": match["list"],
            "reason": match["reason"],
            "severity": match["severity"],
            "added_date": match["added_date"],
            "recommendation": "BLOCK_TRANSACTION",
        })
    
    # Partial match check (for variations like "Ahmed I." or "A. Ivanov")
    for sanctioned_name, data in SANCTIONS_LIST.items():
        name_parts = normalized_name.split()
        sanctioned_parts = sanctioned_name.split()
        
        # Check if all parts of input match parts of sanctioned name
        if len(name_parts) >= 2 and len(sanctioned_parts) >= 2:
            if (name_parts[0] in sanctioned_parts[0] or sanctioned_parts[0] in name_parts[0]) and \
               (name_parts[-1] in sanctioned_parts[-1] or sanctioned_parts[-1] in name_parts[-1]):
                return json.dumps({
                    "is_sanctioned": True,
                    "entity_name": entity_name,
                    "matched_name": sanctioned_name.title(),
                    "match_type": "PARTIAL",
                    "sanctions_list": data["list"],
                    "reason": data["reason"],
                    "severity": data["severity"],
                    "recommendation": "MANUAL_REVIEW",
                })
    
    return json.dumps({
        "is_sanctioned": False,
        "entity_name": entity_name,
        "status": "CLEAN",
        "checked_lists": ["OFAC_SDN", "EU_SANCTIONS", "UN_CONSOLIDATED", "INTERPOL"],
        "recommendation": "PROCEED",
    })


def check_pep_status(person_name: str) -> str:
    """
    Checks if a person is a Politically Exposed Person (PEP).
    
    PEPs require enhanced due diligence under AML regulations.
    
    Args:
        person_name: Full name of the person to check
        
    Returns:
        JSON string with PEP check result
    """
    normalized_name = person_name.lower().strip()
    
    if normalized_name in PEP_LIST:
        match = PEP_LIST[normalized_name]
        return json.dumps({
            "is_pep": True,
            "person_name": person_name,
            "position": match["position"],
            "country": match["country"],
            "risk_level": match["risk_level"],
            "currently_active": match["active"],
            "recommendation": "ENHANCED_DUE_DILIGENCE",
        })
    
    return json.dumps({
        "is_pep": False,
        "person_name": person_name,
        "status": "NOT_PEP",
        "recommendation": "STANDARD_PROCESSING",
    })

