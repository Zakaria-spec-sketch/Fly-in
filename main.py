#!/usr/bin/env python3
"""Command-line entry point for the Fly-in drone routing simulator.

Usage:
    ./main.py <map_file> [--capacity-info] [--no-color]
"""

from __future__ import annotations

import argparse
import sys

from flyin.errors import MapParseError, SimulationError
from flyin.parser import MapParser
from flyin.simulation import Simulation
from flyin.visualizer import Visualizer


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser.

    Returns:
        A configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(
        prog="main.py", description="Route a fleet of drones through a zone network."
    )
    parser.add_argument("map_file", help="path to the map description file")
    parser.add_argument(
        "--capacity-info",
        action="store_true",
        help="display zone/connection capacity usage after each turn",
    )
    parser.add_argument(
        "--no-color", action="store_true", help="disable ANSI colored output"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Optional argument vector (defaults to ``sys.argv[1:]``).

    Returns:
        The process exit code (0 on success, 1 on a handled error).
    """
    args = build_arg_parser().parse_args(argv)

    try:
        graph, nb_drones = MapParser().parse_file(args.map_file)
    except MapParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    visualizer = Visualizer(graph, use_color=not args.no_color)
    visualizer.print_legend()

    try:
        simulation = Simulation(graph, nb_drones, record_capacity_info=args.capacity_info)
        history = simulation.run()
    except SimulationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    for index, moves in enumerate(history, start=1):
        capacity_info = (
            simulation.capacity_snapshots[index - 1] if args.capacity_info else ""
        )
        visualizer.print_turn(index, moves, capacity_info)

    visualizer.print_summary(simulation.stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
