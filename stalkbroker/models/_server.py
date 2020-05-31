import uuid
from dataclasses import dataclass


from typing import Optional


from stalkbroker import constants


@dataclass
class Server:
    """Information about a discord server."""

    id: uuid.UUID
    """stalkbroker id for internal tracking"""
    discord_id: int
    """discord id of the server"""
    bulletin_channel: Optional[int] = None
    """discord id of a server channel to send price bulletins to"""
    bulletin_minimum: int = constants.BULLETIN_MINIMUM
    """the nook offer threshold at which to tag the investor role on price bulletins."""
    heat_minimum: int = constants.HEAT_MINIMUM
    """
    the minimum heat to auto-generate a chart and tag then investor role on forecasts
    after ticker updates.
    """
