import uuid
from dataclasses import dataclass


@dataclass
class Server:
    id: uuid.UUID
    """stalkbroker id for internal tracking"""
    discord_id: int
    """discord id of the server"""
    bulletin_channel: int
    """discord id of a server channel to send price bulletins to"""
