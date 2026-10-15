from typing import Optional
from models import Connection, Zone


class Graph:
    """An undirected graph of :class:`Zone` nodes and :class:`Connection` edges."""

    def __init__(self) -> None:
        """Initialize an empty graph."""
        self._zones: dict[str, Zone] = {}
        self._connections: dict[str, Connection] = {}
        self._adjacency: dict[str, list[Connection]] = {}
        self.start_zone: Optional[str] = None
        self.end_zone: Optional[str] = None

    def add_zone(self, zone: Zone) -> None:
        """Add a zone to the graph.

        Args:
            zone: The zone to register.

        Raises:
            ValueError: If a zone with the same name already exists.
        """
        if zone.name in self._zones:
            raise ValueError(f"duplicate zone name: {zone.name!r}")
        self._zones[zone.name] = zone
        self._adjacency[zone.name] = []
        if zone.is_start:
            self.start_zone = zone.name
        if zone.is_end:
            self.end_zone = zone.name

    def has_zone(self, name: str) -> bool:
        """Whether a zone with the given name exists in the graph."""
        return name in self._zones

    def get_zone(self, name: str) -> Zone:
        """Return the zone registered under ``name``.

        Args:
            name: The zone name.

        Returns:
            The matching :class:`Zone`.

        Raises:
            KeyError: If no such zone exists.
        """
        return self._zones[name]

    def add_connection(self, connection: Connection) -> None:
        """Add a bidirectional connection between two existing zones.

        Args:
            connection: The connection to register.

        Raises:
            ValueError: If either endpoint is unknown or the connection
                already exists (in either direction).
        """
        if connection.zone_a not in self._zones or connection.zone_b not in self._zones:
            raise ValueError(
                f"connection {connection.name!r} references an unknown zone"
            )
        key = self._connection_key(connection.zone_a, connection.zone_b)
        if key in self._connections:
            raise ValueError(f"duplicate connection: {connection.name!r}")
        self._connections[key] = connection
        self._adjacency[connection.zone_a].append(connection)
        self._adjacency[connection.zone_b].append(connection)

    @staticmethod
    def _connection_key(zone_a: str, zone_b: str) -> str:
        """Build an order-independent key identifying a pair of zones."""
        return "|".join(sorted((zone_a, zone_b)))

    def get_connection(self, zone_a: str, zone_b: str) -> Optional[Connection]:
        """Return the connection between two zones, if any.

        Args:
            zone_a: Name of the first zone.
            zone_b: Name of the second zone.

        Returns:
            The :class:`Connection` linking both zones, or ``None``.
        """
        return self._connections.get(self._connection_key(zone_a, zone_b))

    def neighbors(self, zone_name: str) -> list[tuple[str, Connection]]:
        """List the neighboring zones reachable from ``zone_name``.

        Args:
            zone_name: The zone to look up neighbors for.

        Returns:
            A list of ``(neighbor_name, connection)`` tuples.
        """
        result = []
        for connection in self._adjacency.get(zone_name, []):
            result.append((connection.other(zone_name), connection))
        return result

    def __len__(self) -> int:
        """Return the number of zones in the graph."""
        return len(self._zones)
