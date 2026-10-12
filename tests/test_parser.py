"""Unit tests for :mod:`flyin.parser`."""

import pytest

from flyin.errors import MapParseError
from flyin.models import ZoneType
from flyin.parser import MapParser


def test_parses_subject_example() -> None:
    """The subject's own example must parse without error."""
    lines = [
        "nb_drones: 5\n",
        "\n",
        "start_hub: hub 0 0 [color=green]\n",
        "end_hub: goal 10 10 [color=yellow]\n",
        "hub: roof1 3 4 [zone=restricted color=red]\n",
        "hub: roof2 6 2 [zone=normal color=blue]\n",
        "hub: corridorA 4 3 [zone=priority color=green max_drones=2]\n",
        "hub: tunnelB 7 4 [zone=normal color=red]\n",
        "hub: obstacleX 5 5 [zone=blocked color=gray]\n",
        "connection: hub-roof1\n",
        "connection: hub-corridorA\n",
        "connection: roof1-roof2\n",
        "connection: roof2-goal\n",
        "connection: corridorA-tunnelB [max_link_capacity=2]\n",
        "connection: tunnelB-goal\n",
    ]
    graph, nb_drones = MapParser().parse_lines(lines)
    assert nb_drones == 5
    assert graph.start_zone == "hub"
    assert graph.end_zone == "goal"
    assert graph.get_zone("roof1").zone_type is ZoneType.RESTRICTED
    assert graph.get_zone("corridorA").max_drones == 2
    assert graph.get_connection("corridorA", "tunnelB") is not None


def test_comments_are_ignored() -> None:
    """Lines starting with '#' (after stripping) must be ignored."""
    lines = [
        "# a comment\n",
        "nb_drones: 1 # inline comment\n",
        "start_hub: a 0 0\n",
        "end_hub: b 1 0\n",
        "connection: a-b\n",
    ]
    graph, nb_drones = MapParser().parse_lines(lines)
    assert nb_drones == 1
    assert len(graph) == 2


@pytest.mark.parametrize(
    "lines",
    [
        ["start_hub: a 0 0\n", "end_hub: b 1 0\n", "connection: a-b\n"],
        ["nb_drones: 0\n", "start_hub: a 0 0\n", "end_hub: b 1 0\n"],
    ],
)
def test_missing_or_invalid_drone_count(lines: list[str]) -> None:
    """Missing or non-positive drone counts must raise a parse error."""
    with pytest.raises(MapParseError):
        MapParser().parse_lines(lines)


def test_missing_start_hub() -> None:
    """A map without a start_hub must raise a parse error."""
    lines = ["nb_drones: 1\n", "hub: a 0 0\n", "end_hub: b 1 0\n", "connection: a-b\n"]
    with pytest.raises(MapParseError):
        MapParser().parse_lines(lines)


def test_missing_end_hub() -> None:
    """A map without an end_hub must raise a parse error."""
    lines = ["nb_drones: 1\n", "start_hub: a 0 0\n", "hub: b 1 0\n", "connection: a-b\n"]
    with pytest.raises(MapParseError):
        MapParser().parse_lines(lines)


def test_invalid_zone_type() -> None:
    """An unknown zone type must raise a parse error."""
    lines = [
        "nb_drones: 1\n",
        "start_hub: a 0 0\n",
        "end_hub: b 1 0 [zone=weird]\n",
        "connection: a-b\n",
    ]
    with pytest.raises(MapParseError):
        MapParser().parse_lines(lines)


def test_duplicate_connection_rejected() -> None:
    """Both a-b and b-a must be treated as the same, disallowed twice."""
    lines = [
        "nb_drones: 1\n",
        "start_hub: a 0 0\n",
        "end_hub: b 1 0\n",
        "connection: a-b\n",
        "connection: b-a\n",
    ]
    with pytest.raises(MapParseError):
        MapParser().parse_lines(lines)


def test_dash_in_zone_name_rejected() -> None:
    """Zone names must not contain dashes."""
    lines = ["nb_drones: 1\n", "start_hub: a-1 0 0\n", "end_hub: b 1 0\n"]
    with pytest.raises(MapParseError):
        MapParser().parse_lines(lines)


def test_non_positive_capacity_rejected() -> None:
    """max_drones and max_link_capacity must be strictly positive."""
    lines = [
        "nb_drones: 1\n",
        "start_hub: a 0 0\n",
        "end_hub: b 1 0\n",
        "hub: c 2 0 [max_drones=0]\n",
        "connection: a-c\n",
        "connection: c-b\n",
    ]
    with pytest.raises(MapParseError):
        MapParser().parse_lines(lines)


def test_start_end_capacity_metadata_is_ignored() -> None:
    """max_drones on start/end hubs must be accepted but ignored."""
    lines = [
        "nb_drones: 5\n",
        "start_hub: a 0 0 [max_drones=1]\n",
        "end_hub: b 1 0 [max_drones=1]\n",
        "connection: a-b\n",
    ]
    graph, _ = MapParser().parse_lines(lines)
    assert graph.get_zone("a").has_unlimited_capacity
    assert graph.get_zone("b").has_unlimited_capacity
