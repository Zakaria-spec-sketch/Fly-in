from graph import Graph
from models import ZoneType
from simulation import SimulationStats

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"

_COLOR_TABLE: dict[str, str] = {
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "gray": "\033[90m",
    "grey": "\033[90m",
    "orange": "\033[38;5;208m",
}

_TYPE_COLOR: dict[ZoneType, str] = {
    ZoneType.NORMAL: "\033[37m",
    ZoneType.BLOCKED: "\033[90m",
    ZoneType.RESTRICTED: "\033[31m",
    ZoneType.PRIORITY: "\033[32m",
}


class Visualizer:
    """Renders the simulation's progress with colored terminal output."""

    def __init__(self, graph: Graph, use_color: bool = True) -> None:
        """Initialize the visualizer.

        Args:
            graph: The network being simulated, used to resolve zone colors.
            use_color: Whether to emit ANSI color codes at all.
        """
        self.graph = graph
        self.use_color = use_color

    def _style(self, code: str) -> str:
        """Return ``code`` if colors are enabled, else an empty string."""
        return code if self.use_color else ""

    def _colorize(self, text: str, zone_name: str) -> str:
        """Wrap ``text`` in the ANSI color associated with a zone.

        Args:
            text: The text to colorize (usually the zone/connection name).
            zone_name: The zone whose declared or type-based color is used.

        Returns:
            The colorized string, or the original text if colors are
            disabled or the zone is unknown.
        """
        if not self.use_color or not self.graph.has_zone(zone_name):
            return text
        zone = self.graph.get_zone(zone_name)
        code = _COLOR_TABLE.get((zone.color or "").lower()) or _TYPE_COLOR.get(
            zone.zone_type, ""
        )
        if not code:
            return text
        return f"{code}{text}{_RESET}"

    def print_legend(self) -> None:
        """Print a short legend describing the network before simulating."""
        print(f"{self._style(_BOLD)}Fly-in simulation{self._style(_RESET)}")
        print(
            f"  start: {self._colorize(self.graph.start_zone or '?', self.graph.start_zone or '')}"
            f"  ->  end: {self._colorize(self.graph.end_zone or '?', self.graph.end_zone or '')}"
        )
        print(f"  zones: {len(self.graph)}")
        print()

    def print_turn(self, turn_index: int, moves: list[str]) -> None:
        """Print a single simulation turn.

        Args:
            turn_index: 1-indexed turn number.
            moves: The list of ``D<id>-<destination>`` tokens for this turn.
        """
        colored_moves = []
        for token in moves:
            drone_label, _, destination = token.partition("-")
            colored_moves.append(f"{drone_label}-{self._colorize(destination, destination)}")
        prefix = f"{self._style(_DIM)}[turn {turn_index:>3}]{self._style(_RESET)}"
        print(f"{prefix} {' '.join(colored_moves)}")

    def print_summary(self, stats: SimulationStats) -> None:
        """Print the final performance summary panel.

        Args:
            stats: The collected :class:`SimulationStats` for the run.
        """
        print()
        print(f"{self._style(_BOLD)}Simulation complete{self._style(_RESET)}")
        print(f"  total turns        : {stats.total_turns}")
        print(f"  total path cost    : {stats.total_path_cost}")
        print(f"  avg turns / drone  : {stats.average_turns_per_drone:.2f}")
        if stats.moves_per_turn:
            avg_moves = sum(stats.moves_per_turn) / len(stats.moves_per_turn)
            print(f"  avg moves / turn   : {avg_moves:.2f}")
