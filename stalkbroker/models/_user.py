import uuid
import datetime
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class User:
    """User info."""

    id: uuid.UUID
    """Unique id for the user"""
    discord_id: int
    """Discord id of the user"""
    timezone: Optional[datetime.tzinfo] = None
    """Timezone the user is in"""
    servers: List[int] = field(default_factory=list)
    """A list of servers this user is a part of"""
