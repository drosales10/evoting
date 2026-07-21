"""Create or reconcile an explicitly configured administrative bootstrap user."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from sqlalchemy import select

from app.auth.passwords import hash_password
from app.auth.realms import ADMIN_ROLES
from app.core.config import settings
from app.db.session import dispose_engine, get_session_factory
from app.models import AdminUser, AdminUserRole, Organization


async def seed_admin() -> str:
    email = settings.seed_admin_email
    password = settings.seed_admin_password
    full_name = settings.seed_admin_name
    organization_slug = settings.seed_admin_org_slug
    organization_name = settings.seed_admin_org_name
    required = {
        "SEED_ADMIN_EMAIL": email,
        "SEED_ADMIN_PASSWORD": password,
        "SEED_ADMIN_NAME": full_name,
        "SEED_ADMIN_ORG_SLUG": organization_slug,
        "SEED_ADMIN_ORG_NAME": organization_name,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing required bootstrap settings: {', '.join(missing)}")
    assert email is not None
    assert password is not None
    assert full_name is not None
    assert organization_slug is not None
    assert organization_name is not None
    if len(password) < 12:
        raise RuntimeError("SEED_ADMIN_PASSWORD must contain at least 12 characters")
    if settings.seed_admin_role not in ADMIN_ROLES:
        raise RuntimeError(f"Unsupported SEED_ADMIN_ROLE: {settings.seed_admin_role}")

    factory = get_session_factory()
    async with factory() as session:
        organization = await session.scalar(
            select(Organization).where(Organization.slug == organization_slug)
        )
        if organization is None:
            organization = Organization(
                id=uuid4(),
                slug=organization_slug,
                name=organization_name,
            )
            session.add(organization)
            await session.flush()

        admin = await session.scalar(
            select(AdminUser).where(
                AdminUser.organization_id == organization.id,
                AdminUser.email == email,
            )
        )
        if admin is None:
            admin = AdminUser(
                id=uuid4(),
                organization_id=organization.id,
                email=email,
                full_name=full_name,
                password_hash=hash_password(password),
                status="ACTIVE",
                mfa_enabled=True,
            )
            session.add(admin)
            await session.flush()

        role = await session.scalar(
            select(AdminUserRole).where(
                AdminUserRole.admin_user_id == admin.id,
                AdminUserRole.role == settings.seed_admin_role,
            )
        )
        if role is None:
            session.add(
                AdminUserRole(
                    id=uuid4(),
                    admin_user_id=admin.id,
                    role=settings.seed_admin_role,
                )
            )
        await session.commit()
        return (
            f"admin={admin.email}; organization={organization.slug}; "
            f"role={settings.seed_admin_role}"
        )


async def _run() -> int:
    try:
        print(await seed_admin())
    finally:
        await dispose_engine()
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
