import re

def cvsu_email_verification(email: str) -> bool:
    """
    Verify if the provided email belongs to the CVSU domain.
    """
    return email.endswith("@cvsu.edu.ph")

def validate_password_rules(value, rules: dict):
    """
    Generic password validator that checks multiple regex rules.
    `rules` is a dict: { "description": "regex_pattern" }
    """

    for description, pattern in rules.items():
        if not re.search(pattern, value):
            raise ValueError(f"Password must contain {description}")

    return value