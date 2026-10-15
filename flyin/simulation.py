from dataclasses import dataclass, field

from flyin.errors import SimulationError
from flyin.graph import Graph
from flyin.models import Connection, Drone, DroneStatus, Zone, ZoneType
from flyin.pathfinder import PathNotFoundError, Pathfinder

#: A single reservation: (resource key, turn).
_Booking = tuple[str, int]


@dataclass
class SimulationStats:
    """Aggregate, optional performance metrics for a completed simulation."""

    total_turns: int = 0
    total_path_cost: int = 0
    moves_per_turn: list[int] = field(default_factory=list)

    @property
    def average_turns_per_drone(self) -> float:
        """Average number of turns spent per drone (0 if no drones moved)."""
        if not self.moves_per_turn:
            return 0.0
        total_moves = sum(self.moves_per_turn)
        return total_moves / max(1, len(self.moves_per_turn))


class Simulation:
    """Runs the full drone routing simulation over a parsed :class:`Graph`."""

    def __init__(
        self,
        graph: Graph,
        nb_drones: int,
        max_turns: int = 20000,
    ) -> None:
        """Initialize the simulation.

        Args:
            graph: The parsed zone/connection network.
            nb_drones: Number of drones to route from start to end.
            max_turns: Safety cap on the starting turn considered while
                scheduling, guarding against unexpected endless searches.

        Raises:
            SimulationError: If the graph has no start or end zone.
        """
        if graph.start_zone is None or graph.end_zone is None:
            raise SimulationError("graph is missing a start or end zone")
        self.graph = graph
        self.start = graph.start_zone
        self.end = graph.end_zone
        self.max_turns = max_turns
        self.pathfinder = Pathfinder(graph)
        self.drones: list[Drone] = [Drone(i + 1, self.start) for i in range(nb_drones)]

        self.paths: list[list[str]] = []
        #: drone id -> (assigned path, starting turn)
        self.schedules: dict[int, tuple[list[str], int]] = {}
        #: zone name -> turn -> drones present on arrival
        self._zone_schedule: dict[str, dict[int, int]] = {}
        #: connection key -> turn -> drones on the link
        self._connection_schedule: dict[str, dict[int, int]] = {}

        self.history: list[list[str]] = []
        self.stats = SimulationStats()

    # ------------------------------------------------------------------ plan
    def plan(self) -> None:
        """Discover and rank every route from the start to the end zone.

        Raises:
            PathNotFoundError: If the end zone cannot be reached.
        """
        self.paths = self.pathfinder.find_all_paths(self.start, self.end)
        if not self.paths:
            raise PathNotFoundError(f"no path from {self.start!r} to {self.end!r}")

    # -------------------------------------------------------------- schedule
    def schedule_fleet(self) -> None:
        """Assign a path and a starting turn to every drone.

        Drones are handled in order. For each, the best path that can be
        fully booked at the current turn is chosen; if none can, the turn is
        advanced.

        Raises:
            SimulationError: If scheduling exceeds ``max_turns``.
        """
        current_turn = 1
        index = 0
        while index < len(self.drones):
            if current_turn > self.max_turns:
                raise SimulationError(
                    f"scheduling exceeded {self.max_turns} turns without completing"
                )
            drone = self.drones[index]
            for path in self.paths:
                if self._try_book(path, current_turn):
                    self.schedules[drone.drone_id] = (path, current_turn)
                    drone.assign_path(path)
                    self.stats.total_path_cost += Pathfinder.path_cost(self.graph, path)
                    index += 1
                    break
            else:
                current_turn += 1

    def _try_book(self, path: list[str], start_turn: int) -> bool:
        """Check a path's capacity from ``start_turn`` and book it if free.

        Args:
            path: Zone names from start to end.
            start_turn: Turn on which the drone leaves the start zone.

        Returns:
            ``True`` if the whole path was booked, ``False`` if any
            connection or zone lacks capacity at a required turn.
        """
        current_turn = start_turn
        zone_bookings: list[_Booking] = []
        connection_bookings: list[_Booking] = []

        for zone_a, zone_b in zip(path, path[1:]):
            connection = self._connection(zone_a, zone_b)
            next_zone = self.graph.get_zone(zone_b)
            key = self._key(connection)

            if not self._connection_can_carry(connection, current_turn):
                return False
            connection_bookings.append((key, current_turn))

            if next_zone.zone_type == ZoneType.RESTRICTED:
                if not self._connection_can_carry(connection, current_turn + 1):
                    return False
                connection_bookings.append((key, current_turn + 1))
                current_turn += 1

            if not next_zone.has_unlimited_capacity:
                if not self._zone_can_carry(next_zone, current_turn):
                    return False
                zone_bookings.append((next_zone.name, current_turn))

            current_turn += 1

        for name, turn in zone_bookings:
            slots = self._zone_schedule.setdefault(name, {})
            slots[turn] = slots.get(turn, 0) + 1
        for key, turn in connection_bookings:
            link_slots = self._connection_schedule.setdefault(key, {})
            link_slots[turn] = link_slots.get(turn, 0) + 1
        return True

    def _zone_can_carry(self, zone: Zone, turn: int) -> bool:
        """Whether ``zone`` has room for one more drone on ``turn``."""
        used = self._zone_schedule.get(zone.name, {}).get(turn, 0)
        return zone.capacity_for(used + 1)

    def _connection_can_carry(self, connection: Connection, turn: int) -> bool:
        """Whether ``connection`` has room for one more drone on ``turn``."""
        used = self._connection_schedule.get(self._key(connection), {}).get(turn, 0)
        return used < connection.max_link_capacity

    def _connection(self, zone_a: str, zone_b: str) -> Connection:
        """Return the connection between two zones or raise."""
        connection = self.graph.get_connection(zone_a, zone_b)
        if connection is None:
            raise SimulationError(f"no connection between {zone_a!r} and {zone_b!r}")
        return connection

    # ------------------------------------------------------------------- run
    def run(self) -> list[list[str]]:
        """Plan, schedule and replay the whole simulation.

        Returns:
            The list of turns, each a list of ``"D<id>-<destination>"``
            movement tokens (turns with zero movements are omitted).

        Raises:
            SimulationError: If no path exists or scheduling cannot finish.
        """
        self.plan()
        self.schedule_fleet()
        timeline = self._build_timeline()

        self.history = []
        self.stats.moves_per_turn = []
        for turn in sorted(timeline):
            moves = timeline[turn]
            self.history.append(moves)
            self.stats.moves_per_turn.append(len(moves))
        self.stats.total_turns = len(self.history)

        for drone in self.drones:
            drone.status = DroneStatus.DELIVERED
            drone.current_zone = self.end
            drone.path_index = max(0, len(drone.path) - 1)
        return self.history

    def _build_timeline(self) -> dict[int, list[str]]:
        """Replay every booked schedule into per-turn movement tokens.

        Returns:
            A mapping of turn number to the movement tokens of that turn.
        """
        timeline: dict[int, list[str]] = {}
        for drone in self.drones:
            path, current_turn = self.schedules[drone.drone_id]
            for zone_a, zone_b in zip(path, path[1:]):
                connection = self._connection(zone_a, zone_b)
                if self.graph.get_zone(zone_b).zone_type == ZoneType.RESTRICTED:
                    timeline.setdefault(current_turn, []).append(
                        f"{drone.label}-{connection.name}"
                    )
                    current_turn += 1
                timeline.setdefault(current_turn, []).append(f"{drone.label}-{zone_b}")
                current_turn += 1
        return timeline

    @staticmethod
    def _key(connection: Connection) -> str:
        """Build the internal lookup key for a connection."""
        return "|".join(sorted((connection.zone_a, connection.zone_b)))
