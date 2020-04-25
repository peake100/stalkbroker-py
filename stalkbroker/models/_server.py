import uuid
from dataclasses import dataclass


from typing import Optional


@dataclass
class Server:
    """Information about a discord server."""

    id: uuid.UUID
    """stalkbroker id for internal tracking"""
    discord_id: int
    """discord id of the server"""
    bulletin_channel: Optional[int] = None
    """discord id of a server channel to send price bulletins to"""