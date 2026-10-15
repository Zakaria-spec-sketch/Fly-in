import sys

from errors import MapParseError, SimulationError
from parser import MapParser
from simulation import Simulation
from visualizer import Visualizer


def main(argv: list[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Optional argument vector (defaults to ``sys.argv[1:]``).

    Returns:
        The process exit code (0 on success, 1 on a handled error).
    """
    args = sys.argv[1:] if argv is None else argv
    use_color = "--no-color" not in args
    positional = [arg for arg in args if arg != "--no-color"]

    if len(positional) != 1:
        print("usage: main.py <map_file> [--no-color]", file=sys.stderr)
        return 1
    map_file = positional[0]

    try:
        graph, nb_drones = MapParser().parse_file(map_file)
    except MapParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    visualizer = Visualizer(graph, use_color=use_color)
    visualizer.print_legend()

    try:
        simulation = Simulation(graph, nb_drones)
        history = simulation.run()
    except SimulationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    for index, moves in enumerate(history, start=1):
        visualizer.print_turn(index, moves)

    visualizer.print_summary(simulation.stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
