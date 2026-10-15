
import re

from flyin.errors import MapParseError
from flyin.graph import Graph
from flyin.models import Connection, Zone, ZoneType

_ZONE_NAME_RE = re.compile(r"^[^\s\-]+$")
_METADATA_RE = re.compile(r"\[(.*)\]")


class MapParser:
    """Parses a Fly-in map file into a :class:`Graph` and a drone count."""

    def __init__(self) -> None:
        """Initialize an empty parser state."""
        self.nb_drones: int = 0
        self.graph: Graph = Graph()
        self._seen_start = False
        self._seen_end = False

    def parse_file(self, path: str) -> tuple[Graph, int]:
        """Parse a map file from disk.

        Args:
            path: Filesystem path to the map file.

        Returns:
            A tuple ``(graph, nb_drones)``.

        Raises:
            MapParseError: On any malformed or semantically invalid content.
        """
        try:
            with open(path, "r", encoding="utf-8") as handle:
                lines = handle.readlines()
        except OSError as exc:
            raise MapParseError(f"cannot read file {path!r}: {exc}") from exc
        return self.parse_lines(lines)

    def parse_lines(self, lines: list[str]) -> tuple[Graph, int]:
        """Parse map content already split into lines.

        Args:
            lines: The raw lines of the map file, including newlines.

        Returns:
            A tuple ``(graph, nb_drones)``.

        Raises:
            MapParseError: On any malformed or semantically invalid content.
        """
        drone_count_parsed = False
        for line_number, raw_line in enumerate(lines, start=1):
            line = self._strip_comment(raw_line).strip()
            if not line:
                continue
            if not drone_count_parsed:
                self.nb_drones = self._parse_nb_drones(line, line_number)
                drone_count_parsed = True
                continue
            self._parse_directive(line, line_number)

        if not drone_count_parsed:
            raise MapParseError("missing 'nb_drones:' directive")
        if not self._seen_start:
            raise MapParseError("missing 'start_hub:' zone")
        if not self._seen_end:
            raise MapParseError("missing 'end_hub:' zone")
        return self.graph, self.nb_drones

    @staticmethod
    def _strip_comment(raw_line: str) -> str:
        """Remove a trailing ``#`` comment from a raw line."""
        idx = raw_line.find("#")
        if idx == -1:
            return raw_line
        return raw_line[:idx]

    @staticmethod
    def _parse_nb_drones(line: str, line_number: int) -> int:
        """Parse the mandatory ``nb_drones: <n>`` directive.

        Args:
            line: The stripped line content.
            line_number: 1-indexed line number, for error reporting.

        Returns:
            The parsed, positive drone count.

        Raises:
            MapParseError: If the directive is missing or malformed.
        """
        if not line.startswith("nb_drones:"):
            raise MapParseError(
                "expected 'nb_drones: <number>' as the first directive", line_number
            )
        value = line[len("nb_drones:"):].strip()
        if not value.isdigit() or int(value) <= 0:
            raise MapParseError(
                f"invalid drone count {value!r}, expected a positive integer",
                line_number,
            )
        return int(value)

    def _parse_directive(self, line: str, line_number: int) -> None:
        """Dispatch a single non-empty, non-comment line to its handler.

        Args:
            line: The stripped line content.
            line_number: 1-indexed line number, for error reporting.

        Raises:
            MapParseError: If the line does not match any known directive.
        """
        if line.startswith("start_hub:"):
            self._parse_zone_line(line, "start_hub:", line_number, is_start=True)
        elif line.startswith("end_hub:"):
            self._parse_zone_line(line, "end_hub:", line_number, is_end=True)
        elif line.startswith("hub:"):
            self._parse_zone_line(line, "hub:", line_number)
        elif line.startswith("connection:"):
            self._parse_connection_line(line, line_number)
        else:
            raise MapParseError(f"unrecognized directive: {line!r}", line_number)

    def _parse_zone_line(
        self,
        line: str,
        prefix: str,
        line_number: int,
        is_start: bool = False,
        is_end: bool = False,
    ) -> None:
        """Parse a ``start_hub:`` / ``end_hub:`` / ``hub:`` line.

        Args:
            line: The stripped line content.
            prefix: The directive prefix already matched (e.g. ``"hub:"``).
            line_number: 1-indexed line number, for error reporting.
            is_start: Whether this line defines the unique start zone.
            is_end: Whether this line defines the unique end zone.

        Raises:
            MapParseError: On any structural or semantic error.
        """
        if is_start and self._seen_start:
            raise MapParseError("duplicate 'start_hub:' definition", line_number)
        if is_end and self._seen_end:
            raise MapParseError("duplicate 'end_hub:' definition", line_number)

        body, metadata_raw = self._split_metadata(line[len(prefix):].strip(), line_number)
        tokens = body.split()
        if len(tokens) != 3:
            raise MapParseError(
                f"expected '{prefix} <name> <x> <y> [metadata]', got {line!r}",
                line_number,
            )
        name, x_raw, y_raw = tokens
        self._validate_zone_name(name, line_number)
        if self.graph.has_zone(name):
            raise MapParseError(f"duplicate zone name: {name!r}", line_number)
        x = self._parse_int(x_raw, "x coordinate", line_number)
        y = self._parse_int(y_raw, "y coordinate", line_number)

        metadata = self._parse_metadata(metadata_raw, line_number)
        zone_type = self._extract_zone_type(metadata, line_number)
        color = metadata.pop("color", None)
        max_drones = self._extract_max_drones(metadata, line_number, is_start or is_end)
        if metadata:
            unknown = ", ".join(sorted(metadata))
            raise MapParseError(f"unknown zone metadata key(s): {unknown}", line_number)

        zone = Zone(
            name=name,
            x=x,
            y=y,
            zone_type=zone_type,
            color=color,
            max_drones=max_drones,
            is_start=is_start,
            is_end=is_end,
        )
        self.graph.add_zone(zone)
        if is_start:
            self._seen_start = True
        if is_end:
            self._seen_end = True

    def _parse_connection_line(self, line: str, line_number: int) -> None:
        """Parse a ``connection: <a>-<b> [metadata]`` line.

        Args:
            line: The stripped line content.
            line_number: 1-indexed line number, for error reporting.

        Raises:
            MapParseError: On any structural or semantic error.
        """
        body, metadata_raw = self._split_metadata(
            line[len("connection:"):].strip(), line_number
        )
        parts = body.split("-")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise MapParseError(
                f"expected 'connection: <zone1>-<zone2> [metadata]', got {line!r}",
                line_number,
            )
        zone_a, zone_b = parts
        if not self.graph.has_zone(zone_a):
            raise MapParseError(f"connection references unknown zone: {zone_a!r}", line_number)
        if not self.graph.has_zone(zone_b):
            raise MapParseError(f"connection references unknown zone: {zone_b!r}", line_number)
        if zone_a == zone_b:
            raise MapParseError(f"a zone cannot connect to itself: {zone_a!r}", line_number)
        if self.graph.get_connection(zone_a, zone_b) is not None:
            raise MapParseError(
                f"duplicate connection between {zone_a!r} and {zone_b!r}", line_number
            )

        metadata = self._parse_metadata(metadata_raw, line_number)
        capacity = self._extract_positive_int(
            metadata, "max_link_capacity", default=1, line_number=line_number
        )
        if metadata:
            unknown = ", ".join(sorted(metadata))
            raise MapParseError(f"unknown connection metadata key(s): {unknown}", line_number)

        connection = Connection(zone_a, zone_b, max_link_capacity=capacity)
        try:
            self.graph.add_connection(connection)
        except ValueError as exc:
            raise MapParseError(str(exc), line_number) from exc

    @staticmethod
    def _split_metadata(body: str, line_number: int) -> tuple[str, str]:
        """Split a directive body into its main part and metadata block.

        Args:
            body: Directive content after the prefix, e.g. ``"roof1 3 4 [zone=blocked]"``.
            line_number: 1-indexed line number, for error reporting.

        Returns:
            A tuple ``(main_body, metadata_content)`` where ``metadata_content``
            is the text found inside the brackets (empty string if absent).

        Raises:
            MapParseError: If brackets are unbalanced or malformed.
        """
        if "[" not in body and "]" not in body:
            return body.strip(), ""
        match = _METADATA_RE.search(body)
        if not match or body.count("[") != 1 or body.count("]") != 1:
            raise MapParseError("malformed metadata block", line_number)
        if not body.rstrip().endswith("]"):
            raise MapParseError("metadata block must be at the end of the line", line_number)
        main_body = body[: match.start()].strip()
        return main_body, match.group(1).strip()

    @staticmethod
    def _parse_metadata(metadata_raw: str, line_number: int) -> dict[str, str]:
        """Parse a raw ``key=value key2=value2`` metadata string.

        Args:
            metadata_raw: The text found inside brackets.
            line_number: 1-indexed line number, for error reporting.

        Returns:
            A dictionary of metadata key/value pairs.

        Raises:
            MapParseError: If any token is not a valid ``key=value`` pair.
        """
        metadata: dict[str, str] = {}
        if not metadata_raw:
            return metadata
        for token in metadata_raw.split():
            if "=" not in token:
                raise MapParseError(f"malformed metadata token: {token!r}", line_number)
            key, _, value = token.partition("=")
            key = key.strip()
            value = value.strip()
            if not key or not value:
                raise MapParseError(f"malformed metadata token: {token!r}", line_number)
            if key in metadata:
                raise MapParseError(f"duplicate metadata key: {key!r}", line_number)
            metadata[key] = value
        return metadata

    @staticmethod
    def _validate_zone_name(name: str, line_number: int) -> None:
        """Ensure a zone name has no dashes or whitespace.

        Args:
            name: The candidate zone name.
            line_number: 1-indexed line number, for error reporting.

        Raises:
            MapParseError: If the name is empty or contains forbidden characters.
        """
        if not name or not _ZONE_NAME_RE.match(name):
            raise MapParseError(
                f"invalid zone name {name!r}: dashes and spaces are forbidden",
                line_number,
            )

    @staticmethod
    def _parse_int(raw: str, label: str, line_number: int) -> int:
        """Parse a mandatory integer field.

        Args:
            raw: The raw text to parse.
            label: Human readable field name, used in error messages.
            line_number: 1-indexed line number, for error reporting.

        Returns:
            The parsed integer.

        Raises:
            MapParseError: If ``raw`` is not a valid integer.
        """
        try:
            return int(raw)
        except ValueError as exc:
            raise MapParseError(f"invalid {label}: {raw!r}", line_number) from exc

    @staticmethod
    def _extract_positive_int(
        metadata: dict[str, str], key: str, default: int, line_number: int
    ) -> int:
        """Pop and validate a positive-integer metadata field.

        Args:
            metadata: The metadata dictionary (mutated: ``key`` is removed).
            key: The metadata key to extract.
            default: Value to use when the key is absent.
            line_number: 1-indexed line number, for error reporting.

        Returns:
            The validated positive integer.

        Raises:
            MapParseError: If the value is present but not a positive integer.
        """
        if key not in metadata:
            return default
        raw = metadata.pop(key)
        if not raw.isdigit() or int(raw) <= 0:
            raise MapParseError(
                f"{key} must be a positive integer, got {raw!r}", line_number
            )
        return int(raw)

    def _extract_zone_type(self, metadata: dict[str, str], line_number: int) -> ZoneType:
        """Pop and validate the ``zone=<type>`` metadata field.

        Args:
            metadata: The metadata dictionary (mutated: ``zone`` is removed).
            line_number: 1-indexed line number, for error reporting.

        Returns:
            The parsed :class:`ZoneType`, defaulting to ``NORMAL``.

        Raises:
            MapParseError: If the value is not a recognized zone type.
        """
        raw = metadata.pop("zone", None)
        if raw is None:
            return ZoneType.NORMAL
        try:
            return ZoneType.from_string(raw)
        except ValueError as exc:
            raise MapParseError(f"invalid zone type: {raw!r}", line_number) from exc

    def _extract_max_drones(
        self, metadata: dict[str, str], line_number: int, unlimited: bool
    ) -> int:
        """Pop and validate the ``max_drones=<n>`` metadata field.

        Args:
            metadata: The metadata dictionary (mutated: ``max_drones`` is removed).
            line_number: 1-indexed line number, for error reporting.
            unlimited: Whether this zone is the start/end hub, in which case
                the value is accepted but ignored (per the subject).

        Returns:
            The validated positive integer, or ``1`` when unlimited/absent.

        Raises:
            MapParseError: If the value is present but not a positive integer.
        """
        if "max_drones" not in metadata:
            return 1
        raw = metadata.pop("max_drones")
        if not raw.isdigit() or int(raw) <= 0:
            raise MapParseError(
                f"max_drones must be a positive integer, got {raw!r}", line_number
            )
        return 1 if unlimited else int(raw)
