"""
Sanctions and PEP checking tools.
MOCK implementations for demo.
"""
import json

SANCTIONS_LIST = {
    "ahmed ivanov": {"list": "OFAC_SDN", "reason": "Terrorist financing", "severity": "CRITICAL"},
    "shell corp ltd": {"list": "EU_SANCTIONS", "reason": "Money laundering", "severity": "CRITICAL"},
}

PEP_LIST = {
    "elena volkova": {"position": "Deputy Governor", "country": "Regionstan", "risk_level": "HIGH"},
}

def check_sanctions_list(entity_name: str) -> str:
    normalized = entity_name.lower().strip()
    if normalized in SANCTIONS_LIST:
        match = SANCTIONS_LIST[normalized]
        return json.dumps({"is_sanctioned": True, "entity_name": entity_name, **match})
    return json.dumps({"is_sanctioned": False, "entity_name": entity_name, "status": "CLEAN"})

def check_pep_status(person_name: str) -> str:
    normalized = person_name.lower().strip()
    if normalized in PEP_LIST:
        return json.dumps({"is_pep": True, **PEP_LIST[normalized]})
    return json.dumps({"is_pep": False, "person_name": person_name})