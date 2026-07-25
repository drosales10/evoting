from uuid import UUID

from sqlalchemy import Select, and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Election, ElectionBroadcast, ElectionTally

PUBLIC_ELECTION_STATUSES = ("REGISTRATION", "FREEZE", "ACTIVE", "CLOSED", "TALLIED")


class PublicElectionRepository:
    """Read-only queries for data approved for the public portal."""

    def list_published(self, organization_id: UUID | None = None) -> Select[tuple[Election]]:
        # Keep ceremony VOD discoverable even when a pilot/no-quorum tally would
        # otherwise hide a TALLIED election from the public portal.
        has_broadcast = exists(
            select(ElectionBroadcast.id).where(ElectionBroadcast.election_id == Election.id)
        )
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
                    has_broadcast,
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
