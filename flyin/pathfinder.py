"""Pathfinding for the Fly-in network.

Discovers every valid acyclic route from the start hub to the end hub with a
depth-first search, then ranks the routes so the scheduler can try the best
ones first.

Ranking (best first):
    1. least total turn cost,
    2. most priority zones traversed,
    3. fewest zones traversed.

Complexity: the DFS enumerates every simple path, so it is exponential in the
worst case; this is acceptable for the map sizes used by the project.
"""

from __future__ import annotations

from flyin.errors import SimulationError
from flyin.graph import Graph
from flyin.models import ZoneType


class PathNotFoundError(SimulationError):
    """Raised when no valid path exists between the start and end zones."""


class Pathfinder:
    """Discovers and ranks every acyclic path over a :class:`Graph`."""

    def __init__(self, graph: Graph) -> None:
        """Initialize the pathfinder for a given graph.

        Args:
            graph: The network to search over.
        """
        self.graph = graph
        self.all_paths: list[list[str]] = []

    def find_all_paths(self, start: str, end: str) -> list[list[str]]:
        """Extract all valid, non-cyclic paths from ``start`` to ``end``.

        Args:
            start: Name of the origin zone.
            end: Name of the destination zone.

        Returns:
            The discovered paths (lists of zone names, endpoints included),
            sorted from best to worst. Empty if ``end`` is unreachable.
        """
        self.all_paths = []
        self._dfs(start, end, [start], {start})
        return self.sort_paths(self.all_paths)

    def _dfs(self, current: str, end: str, visited: list[str], seen: set[str]) -> None:
        """Recursive depth-first search collecting routes into ``all_paths``.

        Args:
            current: The zone currently being visited.
            end: The destination zone.
            visited: Ordered zones visited so far in the current path.
            seen: Same zones as ``visited``, for constant-time lookups.
        """
        if current == end:
            self.all_paths.append(list(visited))
            return

        for neighbor_name, _connection in self.graph.neighbors(current):
            if neighbor_name in seen:
                continue
            if not self.graph.get_zone(neighbor_name).zone_type.is_accessible:
                continue
            visited.append(neighbor_name)
            seen.add(neighbor_name)
            self._dfs(neighbor_name, end, visited, seen)
            seen.remove(neighbor_name)
            visited.pop()

    def sort_paths(self, paths: list[list[str]]) -> list[list[str]]:
        """Rank paths by cost, priority zone density, then length.

        Args:
            paths: The paths to sort.

        Returns:
            A new list sorted by (least cost, most priority zones,
            fewest zones).
        """

        def path_score(path: list[str]) -> tuple[int, int, int]:
            """Score a single path (lower sorts first)."""
            priority_count = sum(
                -1
                for name in path
                if self.graph.get_zone(name).zone_type == ZoneType.PRIORITY
            )
            return (self.path_cost(self.graph, path), priority_count, len(path))

        return sorted(paths, key=path_score)

    @staticmethod
    def path_cost(graph: Graph, path: list[str]) -> int:
        """Compute the total turn cost of following ``path``.

        Args:
            graph: The network the path belongs to.
            path: A sequence of zone names.

        Returns:
            The sum of entry costs for every zone after the first.
        """
        total = 0
        for zone_name in path[1:]:
            cost = graph.get_zone(zone_name).zone_type.entry_cost
            total += cost if cost is not None else 0
        return total