*This project has been created as part of the 42 curriculum by zmajdoub.*

# Fly-in — Multi-Drone Routing Simulator

## Description

Fly-in routes a fleet of autonomous drones from a central **start** zone to a
target **end** zone through a network of connected zones, in the fewest
possible simulation turns.

The network is described in a small custom text format: zones (`hub`,
`start_hub`, `end_hub`) with an (x, y) position, an optional type
(`normal`, `restricted`, `priority`, `blocked`) and an optional occupancy
limit, and `connection`s between zones with an optional traversal capacity.

The simulator:

- parses and validates the map file (Chapter VI/VII.4 of the subject),
- finds every route through the network with a custom depth-first search
  and ranks them (no third-party graph library is used anywhere),
- schedules every drone on the best available route, respecting zone occupancy limits,
  connection capacity limits and the two-turn "restricted zone" transit
  rule,
- renders the whole simulation with colored terminal output,
- reports the total number of turns and a few secondary performance
  metrics.

## Instructions

No external runtime dependency is required (the simulator only uses the
Python standard library). `flake8`, `mypy` and `pytest` are only needed for
linting/testing.

```bash
# Install dev tooling (flake8, mypy, pytest)
make install

# Run the simulator on a map (defaults to maps/subject_example.txt)
make run
make run MAP=maps/hard_ultimate.txt

# Or directly:
python3 main.py maps/subject_example.txt
python3 main.py maps/subject_example.txt --no-color        # disable ANSI colors

# Debug with pdb
make debug MAP=maps/easy_linear.txt

# Lint / type-check
make lint          # flake8 + mandatory mypy flags
make lint-strict    # flake8 + mypy --strict

# Run the (non-graded) local test suite
make test

# Clean caches
make clean
```

Sample maps for every difficulty tier (`easy_*`, `medium_*`, `hard_*`) are
provided under `maps/`, in addition to the subject's own example
(`maps/subject_example.txt`).

## Algorithm choices and implementation strategy

### Graph

`flyin/graph.py` implements a small, dependency-free undirected graph
(dictionary-based adjacency list). No `networkx`, `graphlib` or similar
library is used anywhere in the project, as required by the subject.

### Pathfinding

`flyin/pathfinder.py` enumerates **every acyclic path** from the start hub
to the end hub with a recursive depth-first search (`blocked` zones are
never entered), then ranks the paths from best to worst by:

1. least total turn cost (`normal` and `priority` zones cost 1 turn to
   enter, `restricted` zones cost 2),
2. most `priority` zones traversed,
3. fewest zones traversed.

The search is exponential in the worst case, but it is fast on the provided
maps.

### Scheduling

`Simulation.schedule_fleet()` (`flyin/simulation.py`) books the drones one
at a time. For each drone it tries the ranked paths from best to worst and
takes the first one whose connections and zones have free capacity at every
turn the drone would need them:

- the connection is checked on the departure turn, and also on the extra
  transit turn when the destination is a `restricted` zone;
- the destination zone is checked on the arrival turn (the start and end
  zones have unlimited capacity);
- if no path fits, the starting turn is advanced and the search repeats.

A booked drone never waits mid-route, so each zone is only occupied on the
turn the drone arrives in it.

### Simulation

`Simulation.run()` replays the booked schedules into a chronological
timeline of movement tokens. A `restricted` zone produces two tokens:
`D1-a-b` while the drone is on the connection, then `D1-b` when it arrives.
The number of printed turns is the total number of simulation steps. A
safety cap (`max_turns`, default 20000) guards against endless scheduling
and raises a clean `SimulationError`.

**Complexity**: path discovery is exponential in the worst case (it lists
every simple path). Booking a drone costs O(P · L) per attempted turn for
`P` paths of length `L`, and the timeline replay is O(D · L) for `D`
drones. Memory is O(P · L + D) for the paths and schedules.

### Object orientation

Every concern is isolated in its own class: `Zone`, `Connection`, `Drone`
(`flyin/models.py`), `Graph` (`flyin/graph.py`), `MapParser`
(`flyin/parser.py`), `Pathfinder` (`flyin/pathfinder.py`), `Simulation`
(`flyin/simulation.py`) and `Visualizer` (`flyin/visualizer.py`). State is
encapsulated behind methods (e.g. `Zone.capacity_for()`,
`Graph.neighbors()`) rather than manipulated directly from outside the
class.

## Visual representation

`flyin/visualizer.py` prints:

- a short legend before the simulation starts (start/end zone, zone
  count), with the start/end zones colored using their declared `color`
  metadata;
- one colored line per turn, e.g. `D1-roof1 D2-corridorA`, where each
  destination is colored according to its declared `color` metadata, or a
  sensible default based on its zone type (red for restricted, green for
  priority, gray for blocked, white for normal) when no color is set;
- a final summary panel with the total number of turns, total path cost,
  and average turns/moves per drone.

`--no-color` disables all ANSI styling for terminals or CI logs that don't
support it.

## Example input and output

Input (`maps/subject_example.txt`, the subject's own example):

```
nb_drones: 5

start_hub: hub 0 0 [color=green]
end_hub: goal 10 10 [color=yellow]
hub: roof1 3 4 [zone=restricted color=red]
hub: roof2 6 2 [zone=normal color=blue]
hub: corridorA 4 3 [zone=priority color=green max_drones=2]
hub: tunnelB 7 4 [zone=normal color=red]
hub: obstacleX 5 5 [zone=blocked color=gray]
connection: hub-roof1
connection: hub-corridorA
connection: roof1-roof2
connection: roof2-goal
connection: corridorA-tunnelB [max_link_capacity=2]
connection: tunnelB-goal
```

Output (`python3 main.py maps/subject_example.txt --no-color`):

```
Fly-in simulation
  start: hub  ->  end: goal
  zones: 7

[turn   1] D1-corridorA D2-hub-roof1
[turn   2] D1-tunnelB D2-roof1 D3-corridorA
[turn   3] D1-goal D2-roof2 D3-tunnelB D4-corridorA D5-hub-roof1
[turn   4] D2-goal D3-goal D4-tunnelB D5-roof1
[turn   5] D4-goal D5-roof2
[turn   6] D5-goal

Simulation complete
  total turns        : 6
  total path cost    : 17
  avg turns / drone  : 2.83
  avg moves / turn   : 2.83
```

Note `D2-hub-roof1` followed by `D2-roof1`: drone D2 enters the
`restricted` zone `roof1` through the `hub-roof1` connection, which takes
exactly two turns as required by the subject.

## Resources

- CLRS, *Introduction to Algorithms* — depth-first search and graph
  traversal theory (general reference, no code copied).
- Python `dataclasses` documentation — used for `SimulationStats`:
  https://docs.python.org/3/library/dataclasses.html
- Python `enum` documentation — used for `ZoneType` / `DroneStatus`:
  https://docs.python.org/3/library/enum.html
- `flake8` / `mypy` documentation for the linting configuration:
  https://flake8.pycqa.org/, https://mypy.readthedocs.io/

### AI usage

AI assistance (Claude) was used to help design and write the initial
implementation of this project end-to-end: the map parser, the custom
graph/DFS pathfinding, the scheduling and simulation engine (occupancy
rules, restricted-zone transit, capacity checks), the colored visualizer,
the Makefile, and the test suite. Every generated module was manually
reviewed, run against the subject's example map and several custom edge
cases (malformed files, blocked/disconnected zones, capacity-1
bottlenecks, high drone counts), and adjusted until `flake8`, `mypy
--strict` and the local `pytest` suite all passed cleanly. No AI-generated
code was accepted without being able to explain what it does and why, per
the project's AI Instructions chapter.