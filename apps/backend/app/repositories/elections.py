from uuid import UUID

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Election, ElectionTally

PUBLIC_ELECTION_STATUSES = ("REGISTRATION", "FREEZE", "ACTIVE", "CLOSED", "TALLIED")


class PublicElectionRepository:
    """Read-only queries for data approved for the public portal."""

    def list_published(self, organization_id: UUID | None = None) -> Select[tuple[Election]]:
        statement = (
            select(Election)
            .outerjoin(ElectionTally, ElectionTally.election_id == Election.id)
            .where(
                Election.status.in_(PUBLIC_ELECTION_STATUSES),
                or_(
                    Election.status != "TALLIED",
                    and_(
                        ElectionTally.quorum_met.is_(True),
                        ElectionTally.pilot_override.is_(False),
                    ),
                ),
            )
        )
        if organization_id is not None:
            statement = statement.where(Election.organization_id == organization_id)
        return statement.order_by(Election.start_time.asc())

    async def fetch_published(
        self,
        session: AsyncSession,
        organization_id: UUID | None = None,
    ) -> list[Election]:
        result = await session.scalars(self.list_published(organization_id))
        return list(result.all())
