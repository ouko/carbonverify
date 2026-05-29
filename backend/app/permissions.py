"""Permission registry and role-to-permission mappings for CarbonVerify."""

from enum import Enum as PyEnum
from typing import List, Set


class Permission(str, PyEnum):
    """Granular permissions for the CarbonVerify platform."""

    # User management
    USERS_READ = "users:read"
    USERS_CREATE = "users:create"
    USERS_UPDATE = "users:update"
    USERS_DELETE = "users:delete"
    USERS_MANAGE_PERMISSIONS = "users:manage_permissions"
    USERS_MANAGE_SESSIONS = "users:manage_sessions"

    # Project management
    PROJECTS_READ = "projects:read"
    PROJECTS_CREATE = "projects:create"
    PROJECTS_UPDATE = "projects:update"
    PROJECTS_DELETE = "projects:delete"

    # Data sources
    DATA_SOURCES_READ = "data_sources:read"
    DATA_SOURCES_CREATE = "data_sources:create"
    DATA_SOURCES_UPDATE = "data_sources:update"
    DATA_SOURCES_DELETE = "data_sources:delete"

    # Calculations
    CALCULATIONS_READ = "calculations:read"
    CALCULATIONS_CREATE = "calculations:create"
    CALCULATIONS_APPROVE = "calculations:approve"
    CALCULATIONS_DELETE = "calculations:delete"

    # Reports
    REPORTS_READ = "reports:read"
    REPORTS_CREATE = "reports:create"
    REPORTS_APPROVE = "reports:approve"
    REPORTS_SUBMIT = "reports:submit"
    REPORTS_DELETE = "reports:delete"

    # Review queue
    REVIEW_QUEUE_READ = "review_queue:read"
    REVIEW_QUEUE_APPROVE = "review_queue:approve"
    REVIEW_QUEUE_ESCALATE = "review_queue:escalate"
    REVIEW_QUEUE_ASSIGN = "review_queue:assign"

    # Field operations
    FIELD_READ = "field:read"
    FIELD_MANAGE_ENUMERATORS = "field:manage_enumerators"

    # Brokerage
    BROKERAGE_READ = "brokerage:read"
    BROKERAGE_TRADE = "brokerage:trade"
    BROKERAGE_MANAGE_LISTINGS = "brokerage:manage_listings"

    # Tokenization
    TOKENIZATION_READ = "tokenization:read"
    TOKENIZATION_MINT = "tokenization:mint"
    TOKENIZATION_RETIRE = "tokenization:retire"
    TOKENIZATION_ADMIN = "tokenization:admin"

    # Corporate
    CORPORATE_READ = "corporate:read"
    CORPORATE_ESG = "corporate:esg"

    # Leads
    LEADS_READ = "leads:read"
    LEADS_MANAGE = "leads:manage"
    LEADS_SCRAPE = "leads:scrape"

    # Compliance
    COMPLIANCE_READ = "compliance:read"
    COMPLIANCE_MANAGE = "compliance:manage"
    COMPLIANCE_ADMIN = "compliance:admin"

    # Audit logs
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"
    AUDIT_ANCHOR = "audit:anchor"

    # Command center / operations
    COMMAND_CENTER_READ = "command_center:read"
    COMMAND_CENTER_MANAGE = "command_center:manage"

    # System
    SYSTEM_CONFIGURE = "system:configure"
    SYSTEM_VIEW_STATS = "system:view_stats"
    SYSTEM_MAINTENANCE = "system:maintenance"


# Default permissions per role
ROLE_PERMISSIONS: dict[str, List[Permission]] = {
    "viewer": [
        Permission.PROJECTS_READ,
        Permission.DATA_SOURCES_READ,
        Permission.CALCULATIONS_READ,
        Permission.REPORTS_READ,
        Permission.REVIEW_QUEUE_READ,
        Permission.FIELD_READ,
        Permission.BROKERAGE_READ,
        Permission.TOKENIZATION_READ,
        Permission.CORPORATE_READ,
        Permission.LEADS_READ,
        Permission.COMPLIANCE_READ,
        Permission.AUDIT_READ,
        Permission.COMMAND_CENTER_READ,
    ],
    "developer": [
        # Inherits viewer permissions
        Permission.PROJECTS_CREATE,
        Permission.DATA_SOURCES_CREATE,
        Permission.CALCULATIONS_CREATE,
        Permission.REPORTS_CREATE,
        Permission.FIELD_MANAGE_ENUMERATORS,
    ],
    "operator": [
        # Inherits developer permissions
        Permission.PROJECTS_UPDATE,
        Permission.DATA_SOURCES_UPDATE,
        Permission.CALCULATIONS_APPROVE,
        Permission.REPORTS_APPROVE,
        Permission.REPORTS_SUBMIT,
        Permission.REVIEW_QUEUE_APPROVE,
        Permission.REVIEW_QUEUE_ESCALATE,
        Permission.REVIEW_QUEUE_ASSIGN,
        Permission.BROKERAGE_TRADE,
        Permission.BROKERAGE_MANAGE_LISTINGS,
        Permission.TOKENIZATION_MINT,
        Permission.TOKENIZATION_RETIRE,
        Permission.CORPORATE_ESG,
        Permission.LEADS_MANAGE,
        Permission.LEADS_SCRAPE,
        Permission.COMPLIANCE_MANAGE,
        Permission.COMMAND_CENTER_MANAGE,
    ],
    "admin": [
        # All permissions
        Permission.USERS_READ,
        Permission.USERS_CREATE,
        Permission.USERS_UPDATE,
        Permission.USERS_DELETE,
        Permission.USERS_MANAGE_PERMISSIONS,
        Permission.USERS_MANAGE_SESSIONS,
        Permission.PROJECTS_DELETE,
        Permission.DATA_SOURCES_DELETE,
        Permission.CALCULATIONS_DELETE,
        Permission.REPORTS_DELETE,
        Permission.TOKENIZATION_ADMIN,
        Permission.COMPLIANCE_ADMIN,
        Permission.AUDIT_EXPORT,
        Permission.AUDIT_ANCHOR,
        Permission.SYSTEM_CONFIGURE,
        Permission.SYSTEM_VIEW_STATS,
        Permission.SYSTEM_MAINTENANCE,
    ],
}


def get_permissions_for_role(role: str) -> Set[str]:
    """Get the complete set of permission strings for a role (including inherited)."""
    role = role.lower()
    perms: Set[str] = set()

    # Build inheritance chain
    chain = ["viewer"]
    if role in ("developer", "operator", "admin"):
        chain.append("developer")
    if role in ("operator", "admin"):
        chain.append("operator")
    if role == "admin":
        chain.append("admin")

    for r in chain:
        perms.update(p.value for p in ROLE_PERMISSIONS.get(r, []))

    return perms


def has_permission(user_role: str, user_permissions: list, required: str) -> bool:
    """Check if a user has a specific permission (via role or explicit grant)."""
    # Admin always has everything
    if user_role == "admin":
        return True

    # Check explicit permissions first
    if required in user_permissions:
        return True

    # Check role-based permissions
    role_perms = get_permissions_for_role(user_role)
    return required in role_perms


def list_all_permissions() -> List[str]:
    """Return all defined permission strings."""
    return [p.value for p in Permission]
