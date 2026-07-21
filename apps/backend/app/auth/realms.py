from typing import Literal

Realm = Literal["ADMIN", "VOTER"]

ADMIN_ACCESS_COOKIE = "evoting_admin_access"
ADMIN_REFRESH_COOKIE = "evoting_admin_refresh"
VOTER_ACCESS_COOKIE = "evoting_voter_access"
VOTER_REFRESH_COOKIE = "evoting_voter_refresh"

ADMIN_ROLES = frozenset({"SUPER_ADMIN", "ELECTORAL_JUSTICE", "PARTY_PROXY", "CANDIDATE"})
VOTER_ROLE = "MEMBER"
