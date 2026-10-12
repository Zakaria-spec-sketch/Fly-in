"""Domain models for the Fly-in drone routing simulator.

This module defines the core, dependency-free data types used throughout the
project: zone types, zones, connections and drones. No graph *algorithms*
live here; :mod:`flyin.graph` builds on top of these primitives.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional


class ZoneType(Enum):
    """Enumerates the four valid zone types and their movement cost rules."""

    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"

    @classmethod
    def from_string(cls, raw: str) -> "ZoneType":
        """Parse a zone type from its textual representation.

        Args:
            raw: The raw string found in the map file (e.g. ``"restricted"``).

        Returns:
            The matching :class:`ZoneType` member.

        Raises:
            ValueError: If ``raw`` does not match any known zone type.
        """
        for member in cls:
            if member.value == raw:
                return member
        raise ValueError(f"invalid zone type: {raw!r}")

    @property
    def entry_cost(self) -> Optional[int]:
        """Return the number of turns required to enter a zone of this type.

        Returns:
            The turn cost, or ``None`` if the zone type is inaccessible
            (:attr:`BLOCKED`).
        """
        costs = {
            ZoneType.NORMAL: 1,
            ZoneType.RESTRICTED: 2,
            ZoneType.PRIORITY: 1,
            ZoneType.BLOCKED: None,
        }
        return costs[self]

    @property
    def is_accessible(self) -> bool:
        """Whether drones are allowed to enter a zone of this type."""
        return self is not ZoneType.BLOCKED

    @property
    def is_preferred(self) -> bool:
        """Whether pathfinding should favour this zone type when tied."""
        return self is ZoneType.PRIORITY


class Zone:
    """A single zone (node) in the drone routing network."""

    def __init__(
        self,
        name: str,
        x: int,
        y: int,
        zone_type: ZoneType = ZoneType.NORMAL,
        color: Optional[str] = None,
        max_drones: int = 1,
        is_start: bool = False,
        is_end: bool = False,
    ) -> None:
        """Initialize a zone.

        Args:
            name: Unique identifier of the zone.
            x: X coordinate (used for display purposes only).
            y: Y coordinate (used for display purposes only).
            zone_type: The zone's type, governing entry cost and access.
            color: Optional display color.
            max_drones: Maximum number of drones allowed simultaneously.
                Ignored (treated as unlimited) for start/end zones.
            is_start: Whether this zone is the unique start hub.
            is_end: Whether this zone is the unique end hub.
        """
        self.name = name
        self.x = x
        self.y = y
        self.zone_type = zone_type
        self.color = color
        self.is_start = is_start
        self.is_end = is_end
        self.max_drones = max_drones

    @property
    def has_unlimited_capacity(self) -> bool:
        """Whether this zone may hold an unlimited number of drones."""
        return self.is_start or self.is_end

    def capacity_for(self, requested: int) -> bool:
        """Check whether ``requested`` simultaneous occupants are allowed.

        Args:
            requested: Number of drones that would occupy the zone at once.

        Returns:
            ``True`` if the zone can hold that many drones simultaneously.
        """
        if self.has_unlimited_capacity:
            return True
        return requested <= self.max_drones

    def __repr__(self) -> str:
        """Return a debug-friendly representation of the zone."""
        return f"Zone({self.name}, type={self.zone_type.value})"


class Connection:
    """A bidirectional edge between two zones."""

    def __init__(self, zone_a: str, zone_b: str, max_link_capacity: int = 1) -> None:
        """Initialize a connection between two zone names.

        Args:
            zone_a: Name of the first endpoint zone.
            zone_b: Name of the second endpoint zone.
            max_link_capacity: Maximum drones allowed to traverse this
                connection during the same turn.
        """
        self.zone_a = zone_a
        self.zone_b = zone_b
        self.max_link_capacity = max_link_capacity

    @property
    def name(self) -> str:
        """Return the canonical display name of the connection."""
        return f"{self.zone_a}-{self.zone_b}"

    def other(self, zone_name: str) -> str:
        """Return the endpoint on the other side of ``zone_name``.

        Args:
            zone_name: Name of one of the connection's endpoints.

        Returns:
            The name of the opposite endpoint.

        Raises:
            ValueError: If ``zone_name`` is not an endpoint of this connection.
        """
        if zone_name == self.zone_a:
            return self.zone_b
        if zone_name == self.zone_b:
            return self.zone_a
        raise ValueError(f"{zone_name!r} is not an endpoint of {self.name!r}")

    def connects(self, zone_name: str) -> bool:
        """Whether ``zone_name`` is one of this connection's endpoints."""
        return zone_name in (self.zone_a, self.zone_b)

    def __repr__(self) -> str:
        """Return a debug-friendly representation of the connection."""
        return f"Connection({self.zone_a!r}-{self.zone_b!r}, cap={self.max_link_capacity})"


class DroneStatus(Enum):
    """Lifecycle states of a drone during the simulation."""

    WAITING_AT_START = "waiting_at_start"
    IN_ZONE = "in_zone"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"


class Drone:
    """A single drone travelling through the network."""

    def __init__(self, drone_id: int, start_zone: str) -> None:
        """Initialize a drone at the start zone.

        Args:
            drone_id: Unique numeric identifier for the drone.
            start_zone: Name of the zone the drone begins in.
        """
        self.drone_id = drone_id
        self.current_zone: Optional[str] = start_zone
        self.status = DroneStatus.WAITING_AT_START
        self.path: list[str] = []
        self.path_index: int = 0
        self.transit_connection: Optional[Connection] = None
        self.transit_remaining: int = 0
        self.transit_destination: Optional[str] = None
        self.wait_streak: int = 0

    @property
    def label(self) -> str:
        """Return the display identifier used in simulation output (e.g. D3)."""
        return f"D{self.drone_id}"

    @property
    def is_delivered(self) -> bool:
        """Whether the drone has reached the end zone."""
        return self.status is DroneStatus.DELIVERED

    def assign_path(self, path: list[str]) -> None:
        """Assign the sequence of zone names this drone should follow.

        Args:
            path: A list of zone names starting at the start zone and
                ending at the end zone.
        """
        self.path = path
        self.path_index = 0

    def next_target(self) -> Optional[str]:
        """Return the next zone this drone should move towards, if any."""
        if self.path_index + 1 >= len(self.path):
            return None
        return self.path[self.path_index + 1]

    def __repr__(self) -> str:
        """Return a debug-friendly representation of the drone."""
        return f"Drone({self.label}, at={self.current_zone}, status={self.status.value})"
