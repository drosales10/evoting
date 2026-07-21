import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import (
    AdminMfaCredential,
    AdminUser,
    AdminUserRole,
    AuthSession,
    Organization,
)


@dataclass(frozen=True)
class AdminUserRecord:
    id: UUID
    organization_id: UUID
    password_hash: str
    status: str
    mfa_enabled: bool
    roles: tuple[str, ...]


@dataclass(frozen=True)
class SessionCredentials:
    session: AuthSession
    refresh_token: str
    csrf_token: str


class AdminUserRepository:
    async def find_by_credentials(
        self,
        session: AsyncSession,
        organization_slug: str,
        email: str,
    ) -> AdminUserRecord | None:
        statement = (
            select(AdminUser)
            .join(Organization, Organization.id == AdminUser.organization_id)
            .where(
                Organization.slug == organization_slug,
                func.lower(AdminUser.email) == email.strip().lower(),
            )
        )
        user = await session.scalar(statement)
        if user is None:
            return None

        role_statement = select(AdminUserRole.role).where(AdminUserRole.admin_user_id == user.id)
        roles = tuple(await session.scalars(role_statement))
        return AdminUserRecord(
            id=user.id,
            organization_id=user.organization_id,
            password_hash=user.password_hash,
            status=user.status,
            mfa_enabled=user.mfa_enabled,
            roles=roles,
        )

    async def find_mfa_credential(
        self,
        session: AsyncSession,
        admin_user_id: UUID,
    ) -> AdminMfaCredential | None:
        statement = select(AdminMfaCredential).where(
            AdminMfaCredential.admin_user_id == admin_user_id
        )
        result = await session.scalars(statement)
        return result.first()

    async def enroll_mfa(
        self,
        session: AsyncSession,
        user: AdminUserRecord,
        encrypted_secret: str,
    ) -> bool:
        # Lock the parent row so two concurrent enrollment requests cannot both win.
        await session.execute(select(AdminUser.id).where(AdminUser.id == user.id).with_for_update())
        existing = await self.find_mfa_credential(session, user.id)
        if existing is not None:
            await session.rollback()
            return False

        session.add(
            AdminMfaCredential(
                admin_user_id=user.id,
                organization_id=user.organization_id,
                encrypted_secret=encrypted_secret,
            )
        )
        await session.commit()
        return True

    async def consume_mfa_counter(
        self,
        session: AsyncSession,
        admin_user_id: UUID,
        counter: int,
    ) -> bool:
        statement = (
            update(AdminMfaCredential)
            .where(
                AdminMfaCredential.admin_user_id == admin_user_id,
                or_(
                    AdminMfaCredential.last_used_counter.is_(None),
                    AdminMfaCredential.last_used_counter < counter,
                ),
            )
            .values(last_used_counter=counter, confirmed_at=func.now())
        )
        result = await session.execute(statement)
        if result.rowcount != 1:
            await session.rollback()
            return False
        return True

    async def create_session(
        self,
        session: AsyncSession,
        user: AdminUserRecord,
    ) -> SessionCredentials:
        now = datetime.now(UTC)
        refresh_token = secrets.token_urlsafe(48)
        csrf_token = secrets.token_urlsafe(32)
        auth_session = AuthSession(
            id=uuid4(),
            organization_id=user.organization_id,
            principal_id=user.id,
            realm="ADMIN",
            refresh_token_hash=sha256(refresh_token.encode("utf-8")).hexdigest(),
            csrf_token_hash=sha256(csrf_token.encode("utf-8")).hexdigest(),
            expires_at=now + timedelta(days=settings.refresh_token_days),
        )
        session.add(auth_session)
        await session.commit()
        return SessionCredentials(auth_session, refresh_token, csrf_token)
