"""Idempotent seed for the system developer used by registry-imported projects."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import get_password_hash
from app.core.encryption import compute_searchable_hash
from app.core.logging import get_logger
from app.models import Developer, User

logger = get_logger(__name__)

SYSTEM_DEVELOPER_EMAIL = "registry-imports@carbonverify.internal"
SYSTEM_DEVELOPER_NAME = "Registry Imports"
SYSTEM_COMPANY_NAME = "CarbonVerify Registry Imports"
# Inactive system user cannot authenticate, but a non-null password hash is required
# by the schema, so store a secure dummy hash.
_SYSTEM_DUMMY_PASSWORD = "carbonverify-system-developer-no-login"


async def get_or_create_system_developer(db: AsyncSession) -> Developer:
    """Return the system developer, creating it (and a backing user) if absent."""
    email_hash = compute_searchable_hash(SYSTEM_DEVELOPER_EMAIL)

    result = await db.execute(select(User).where(User.email_hash == email_hash))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            email=SYSTEM_DEVELOPER_EMAIL,
            email_hash=email_hash,
            name=SYSTEM_DEVELOPER_NAME,
            role="developer",
            is_active=False,
            hashed_password=get_password_hash(_SYSTEM_DUMMY_PASSWORD),
        )
        db.add(user)
        await db.flush()
        logger.info("system_user_created", user_id=str(user.id))

    dev_result = await db.execute(select(Developer).where(Developer.user_id == user.id))
    developer = dev_result.scalar_one_or_none()
    if developer is None:
        developer = Developer(
            user_id=user.id,
            company_name=SYSTEM_COMPANY_NAME,
        )
        db.add(developer)
        await db.flush()
        logger.info("system_developer_created", developer_id=str(developer.id))

    return developer
