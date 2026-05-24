"""
Field-level data masking for sensitive information.

Implements role-based masking of GPS coordinates, household identifiers,
and other PII according to the Kenya Data Protection Act requirements.
"""

import re
from typing import Any, Dict, Optional
from enum import Enum as PyEnum

from app.models import User, UserRoleEnum


class SensitivityLevel(PyEnum):
    public = "public"
    internal = "internal"
    confidential = "confidential"
    restricted = "restricted"


# Field sensitivity mapping
FIELD_SENSITIVITY = {
    "gps_latitude": SensitivityLevel.restricted,
    "gps_longitude": SensitivityLevel.restricted,
    "household_id": SensitivityLevel.confidential,
    "stove_id": SensitivityLevel.confidential,
    "phone_number": SensitivityLevel.confidential,
    "email": SensitivityLevel.confidential,
    "contact_phone": SensitivityLevel.confidential,
    "enumerator_name": SensitivityLevel.internal,
    "village_name": SensitivityLevel.internal,
    "exact_location": SensitivityLevel.restricted,
    "biometric_data": SensitivityLevel.restricted,
    "financial_details": SensitivityLevel.restricted,
}

# Role-based access levels
ROLE_ACCESS_LEVELS = {
    UserRoleEnum.admin: SensitivityLevel.restricted,
    UserRoleEnum.operator: SensitivityLevel.confidential,
    UserRoleEnum.developer: SensitivityLevel.internal,
    UserRoleEnum.viewer: SensitivityLevel.public,
}


def mask_gps(coordinate: Optional[float], precision: int = 2) -> Optional[float]:
    """
    Reduce GPS precision to mask exact location.

    Admin: full precision
    Operator: ~1km precision (2 decimal places)
    Developer: ~11km precision (1 decimal place)
    Viewer: hidden
    """
    if coordinate is None:
        return None
    return round(coordinate, precision)


def mask_id(identifier: Optional[str], visible_chars: int = 4) -> Optional[str]:
    """Mask an identifier showing only last N characters."""
    if not identifier:
        return None
    if len(identifier) <= visible_chars:
        return "*" * len(identifier)
    return "*" * (len(identifier) - visible_chars) + identifier[-visible_chars:]


def mask_email(email: Optional[str]) -> Optional[str]:
    """Mask email address."""
    if not email:
        return None
    parts = email.split("@")
    if len(parts) != 2:
        return "*" * len(email)
    local, domain = parts
    masked_local = local[0] + "*" * (len(local) - 1) if len(local) > 1 else "*"
    return f"{masked_local}@{domain}"


def mask_phone(phone: Optional[str], visible: int = 3) -> Optional[str]:
    """Mask phone number showing only last N digits."""
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if len(digits) <= visible:
        return "*" * len(digits)
    return "*" * (len(digits) - visible) + digits[-visible:]


def mask_field(field_name: str, value: Any, user_role: UserRoleEnum) -> Any:
    """Mask a single field based on its sensitivity and user role."""
    sensitivity = FIELD_SENSITIVITY.get(field_name, SensitivityLevel.public)
    user_level = ROLE_ACCESS_LEVELS.get(user_role, SensitivityLevel.public)

    # If user's access level >= field sensitivity, no masking needed
    sensitivity_order = [SensitivityLevel.public, SensitivityLevel.internal,
                         SensitivityLevel.confidential, SensitivityLevel.restricted]
    if sensitivity_order.index(user_level) >= sensitivity_order.index(sensitivity):
        return value

    # Apply masking based on field type
    if field_name in ("gps_latitude", "gps_longitude"):
        if user_level == SensitivityLevel.confidential:
            return mask_gps(value, precision=2)
        elif user_level == SensitivityLevel.internal:
            return mask_gps(value, precision=1)
        else:
            return None

    if field_name in ("household_id", "stove_id"):
        if user_level == SensitivityLevel.internal:
            return mask_id(value, visible_chars=4)
        return mask_id(value, visible_chars=2)

    if field_name == "email":
        return mask_email(value)

    if field_name in ("phone_number", "contact_phone"):
        return mask_phone(value)

    if field_name in ("enumerator_name", "village_name"):
        if user_level == SensitivityLevel.public:
            return "[REDACTED]"
        return mask_id(value, visible_chars=3)

    # Default: redact
    return "[REDACTED]"


def mask_data(data: Dict[str, Any], user_role: UserRoleEnum, fields_to_mask: Optional[list] = None) -> Dict[str, Any]:
    """
    Mask sensitive fields in a data dictionary.

    Args:
        data: The data dictionary to mask
        user_role: The role of the requesting user
        fields_to_mask: Specific fields to mask (if None, uses FIELD_SENSITIVITY mapping)

    Returns:
        A new dictionary with masked values
    """
    if not isinstance(data, dict):
        return data

    result = {}
    for key, value in data.items():
        if fields_to_mask and key in fields_to_mask:
            result[key] = mask_field(key, value, user_role)
        elif key in FIELD_SENSITIVITY:
            result[key] = mask_field(key, value, user_role)
        else:
            result[key] = value
    return result


def mask_survey_response(response: Dict[str, Any], user_role: UserRoleEnum) -> Dict[str, Any]:
    """Mask a survey response according to role."""
    sensitive_fields = ["gps_latitude", "gps_longitude", "household_id", "stove_id",
                        "phone_number", "village_name", "exact_location"]
    return mask_data(response, user_role, fields_to_mask=sensitive_fields)


def mask_enumerator_data(enumerator: Dict[str, Any], user_role: UserRoleEnum) -> Dict[str, Any]:
    """Mask enumerator data according to role."""
    sensitive_fields = ["phone_number", "name", "contact_phone", "exact_location"]
    return mask_data(enumerator, user_role, fields_to_mask=sensitive_fields)
