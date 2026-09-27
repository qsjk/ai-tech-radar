"""Functional configuration files `config/` (IV §16, docs/architecture.md §3.2).

- `load_config_files(path)` loads the four files: for the worker and `validate-config`.
- `load_pipeline(path)` loads `pipeline.yaml` alone, read-only: for the app (E17).
- Any error raises `ConfigError`, which lists each problem with **file, key and field** (IV §16.5).

Sprint 1 schemas (`schemas` part of T-CFG-02). The source type, `poll_interval` and `config` stay free-form fields
until the collector registry (Sprint 2). `pipeline.yaml` only declares the sections used in Sprint 1; the others come
with their stage (E6).
"""

import re
from collections.abc import Hashable, Iterable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Any, Literal, Self

import yaml
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError, field_validator, model_validator

SOURCES_FILE = "sources.yaml"
TOPICS_FILE = "topics.yaml"
ENTITIES_FILE = "entities.yaml"
PIPELINE_FILE = "pipeline.yaml"

SOURCE_KEY = r"^[a-z0-9-]+$"  # IV §16.2

# ── Errors ────────────────────────────────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ConfigIssue:
    """A configuration problem: file, entry (key), field, message."""

    file: str
    key: str | None
    field: str | None
    message: str

    def __str__(self) -> str:
        parts = [self.file]
        if self.key is not None:
            parts.append(f"entry '{self.key}'")
        if self.field is not None:
            parts.append(f"field '{self.field}'")
        return " · ".join(parts) + f": {self.message}"


class ConfigError(Exception):
    """Invalid configuration: one or more problems, each with file, key and field."""

    def __init__(self, issues: Iterable[ConfigIssue]) -> None:
        self.issues = list(issues)
        super().__init__("\n".join(str(issue) for issue in self.issues))


# ── Safe YAML loading, duplicate keys rejected ────────────────────────────────────────────────────────────────────────


class _DuplicateKeyError(yaml.YAMLError):
    pass


class _StrictLoader(yaml.SafeLoader):
    """Safe loader that rejects a key repeated in the same mapping (otherwise PyYAML silently keeps the last one)."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Hashable, Any]:
        seen: set[Any] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                mark = key_node.start_mark
                raise _DuplicateKeyError(f"key '{key}' repeated in the same mapping (line {mark.line + 1})")
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def _read_yaml(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError([ConfigIssue(path.name, None, None, "required file missing")]) from None
    try:
        return yaml.load(text, Loader=_StrictLoader)  # noqa: S506 — loader derived from SafeLoader
    except _DuplicateKeyError as error:
        raise ConfigError([ConfigIssue(path.name, None, None, str(error))]) from None
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        where = f" (line {mark.line + 1}, column {mark.column + 1})" if mark is not None else ""
        problem = getattr(error, "problem", None) or str(error)
        raise ConfigError([ConfigIssue(path.name, None, None, f"invalid YAML syntax{where}: {problem}")]) from None


# ── Common types ──────────────────────────────────────────────────────────────────────────────────────────────────────

_DURATION = re.compile(r"^\s*(\d+)\s*(s|m|h|d)\s*$")
_UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}


def _parse_duration(value: Any) -> Any:
    """Duration written as in the spec (`120s`, `15m`, `2h`, `30d`), or an integer number of seconds."""
    if isinstance(value, bool):
        raise ValueError("duration expected, for example 120s, 15m or 2h")
    if isinstance(value, int):
        return timedelta(seconds=value)
    if isinstance(value, str):
        match = _DURATION.match(value)
        if match:
            return timedelta(**{_UNITS[match.group(2)]: int(match.group(1))})
    if isinstance(value, timedelta):
        return value
    raise ValueError("duration expected, for example 120s, 15m or 2h")


Duration = Annotated[timedelta, BeforeValidator(_parse_duration)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Keyword(_Model):
    """Matching term: a string, or `{term, weight, regex}` (IV §16.3)."""

    term: str = Field(min_length=1)
    weight: float = Field(default=1, gt=0)
    regex: bool = False

    @model_validator(mode="after")
    def _compile_regex(self) -> Self:
        if self.regex:
            try:
                re.compile(self.term)
            except re.error as error:
                raise ValueError(f"invalid regex '{self.term}': {error}") from None
        return self


def _keyword(value: Any) -> Any:
    return {"term": value} if isinstance(value, str) else value


KeywordEntry = Annotated[Keyword, BeforeValidator(_keyword)]

# ── Files ─────────────────────────────────────────────────────────────────────────────────────────────────────────────


class SourceSpec(_Model):
    """Entry of `sources.yaml` (IV §16.2)."""

    key: str = Field(pattern=SOURCE_KEY)
    name: str = Field(min_length=1)
    type: str = Field(min_length=1)  # checked by the collector registry in Sprint 2
    url: str = Field(min_length=1)
    enabled: bool = True
    poll_interval: Duration | None = None  # per-type minimum checked in Sprint 2
    relevance: Literal["filter", "always"] = "filter"
    extract: Literal["auto", "never"] | None = None
    config: dict[str, Any] = Field(default_factory=dict)  # validated by the collector in Sprint 2


class SourcesFile(_Model):
    sources: list[SourceSpec]


class TopicSpec(_Model):
    """Entry of `topics.yaml` (IV §16.3)."""

    slug: str = Field(min_length=1)  # IV §16.3: unique, no enforced format
    name: str = Field(min_length=1)
    description: str | None = None
    parent: str | None = None
    enabled: bool = True
    keywords: list[KeywordEntry] = Field(min_length=1)
    exclude: list[str] = Field(default_factory=list)


class TopicsFile(_Model):
    topics: list[TopicSpec]


class EntitySpec(_Model):
    """Entry of `entities.yaml` (IV §16.4)."""

    type: Literal["company", "product", "person", "project", "technology", "model", "repository"]
    canonical_name: str = Field(min_length=1)
    name: str = Field(min_length=1)
    aliases: list[KeywordEntry] = Field(default_factory=list)

    @field_validator("canonical_name")
    @classmethod
    def _lowercase(cls, value: str) -> str:
        if value != value.lower():
            raise ValueError("canonical_name must be lowercase")
        return value


class EntitiesFile(_Model):
    entities: list[EntitySpec]
    github_reserved_paths: list[str] = Field(default_factory=list)


WATCHDOG_TIMEOUT_MIN = timedelta(seconds=10)
"""Minimum of `ops.watchdog_timeout`: twice the watchdog refresh period (5 s). Below it, a healthy worker would be
stopped (decision of 2026-09-27)."""


class OpsSettings(_Model):
    """`ops` section of `pipeline.yaml`, settings used in Sprint 1 (VII §39.7)."""

    heartbeat_interval: Duration = timedelta(seconds=30)
    heartbeat_stale_after: Duration = timedelta(seconds=120)
    watchdog_timeout: Duration = timedelta(seconds=300)

    @field_validator("watchdog_timeout")
    @classmethod
    def _watchdog_timeout_min(cls, value: timedelta) -> timedelta:
        if value < WATCHDOG_TIMEOUT_MIN:
            minimum = int(WATCHDOG_TIMEOUT_MIN.total_seconds())
            raise ValueError(
                f"at least {minimum}s expected, twice the watchdog refresh period (5 s); "
                "below it, a healthy worker would be stopped"
            )
        return value


class PipelineConfig(_Model):
    """`pipeline.yaml`: optional, missing → defaults (IV §16.5). Sections added sprint by sprint (E6)."""

    ops: OpsSettings = Field(default_factory=OpsSettings)


@dataclass(frozen=True)
class ConfigFiles:
    sources: SourcesFile
    topics: TopicsFile
    entities: EntitiesFile
    pipeline: PipelineConfig


# ── Validation ────────────────────────────────────────────────────────────────────────────────────────────────────────


def _entry_key(file: str, data: Any, loc: tuple[int | str, ...]) -> tuple[str | None, str | None]:
    """Translate the Pydantic location into (entry key, field)."""
    if file == PIPELINE_FILE:
        return (str(loc[0]) if loc else None), (".".join(str(p) for p in loc[1:]) or None)
    if len(loc) < 2 or not isinstance(loc[1], int):
        return None, (".".join(str(p) for p in loc) or None)
    index = loc[1]
    entry: Any = None
    if isinstance(data, dict):
        items = data.get(str(loc[0]))
        if isinstance(items, list) and index < len(items):
            entry = items[index]
    key: str | None = None
    if isinstance(entry, dict):
        if file == SOURCES_FILE:
            key = entry.get("key")
        elif file == TOPICS_FILE:
            key = entry.get("slug")
        elif file == ENTITIES_FILE and entry.get("canonical_name"):
            key = f"{entry.get('type')}:{entry.get('canonical_name')}"
    field = ".".join(str(p) for p in loc[2:]) or None
    return (str(key) if key else f"#{index + 1}"), field


def _validate[M: BaseModel](model: type[M], file: str, data: Any) -> M:
    if data is None:
        data = {}
    try:
        return model.model_validate(data)
    except ValidationError as error:
        issues = []
        for detail in error.errors():
            key, field = _entry_key(file, data, tuple(detail["loc"]))
            message = str(detail["msg"]).removeprefix("Value error, ")
            issues.append(ConfigIssue(file, key, field, message))
        raise ConfigError(issues) from None


def _check_sources(sources: SourcesFile) -> list[ConfigIssue]:
    return [
        ConfigIssue(SOURCES_FILE, key, "key", "duplicate key")
        for key in _duplicates(source.key for source in sources.sources)
    ]


def _check_topics(topics: TopicsFile) -> list[ConfigIssue]:
    issues = [
        ConfigIssue(TOPICS_FILE, slug, "slug", "duplicate slug") for slug in _duplicates(t.slug for t in topics.topics)
    ]
    parents = {topic.slug: topic.parent for topic in topics.topics}
    for topic in topics.topics:
        if topic.parent is not None and topic.parent not in parents:
            issues.append(ConfigIssue(TOPICS_FILE, topic.slug, "parent", f"parent '{topic.parent}' does not exist"))
    reported: set[str] = set()
    for start in parents:
        path, current = [start], parents.get(start)
        while current is not None and current in parents and current not in path:
            path.append(current)
            current = parents[current]
        if current is not None and current in path:
            cycle = path[path.index(current) :]
            if not reported.intersection(cycle):
                reported.update(cycle)
                chain = " → ".join([*cycle, current])
                issues.append(ConfigIssue(TOPICS_FILE, current, "parent", f"parent cycle: {chain}"))
    return issues


def _check_entities(entities: EntitiesFile) -> list[ConfigIssue]:
    keys = (f"{entity.type}:{entity.canonical_name}" for entity in entities.entities)
    return [
        ConfigIssue(ENTITIES_FILE, key, "canonical_name", "duplicate (type, canonical_name)")
        for key in _duplicates(keys)
    ]


def _duplicates(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    repeated: list[str] = []
    for value in values:
        if value in seen and value not in repeated:
            repeated.append(value)
        seen.add(value)
    return repeated


def load_pipeline(path: Path) -> PipelineConfig:
    """Load `pipeline.yaml` from the `path` directory; missing → defaults."""
    file = path / PIPELINE_FILE
    if not file.exists():
        return PipelineConfig()
    return _validate(PipelineConfig, PIPELINE_FILE, _read_yaml(file))


def load_config_files(path: Path) -> ConfigFiles:
    """Load and validate the four files of the `path` directory. Collect every problem before raising."""
    issues: list[ConfigIssue] = []
    sources = topics = entities = None
    try:
        sources = _validate(SourcesFile, SOURCES_FILE, _read_yaml(path / SOURCES_FILE))
        issues.extend(_check_sources(sources))
    except ConfigError as error:
        issues.extend(error.issues)
    try:
        topics = _validate(TopicsFile, TOPICS_FILE, _read_yaml(path / TOPICS_FILE))
        issues.extend(_check_topics(topics))
    except ConfigError as error:
        issues.extend(error.issues)
    try:
        entities = _validate(EntitiesFile, ENTITIES_FILE, _read_yaml(path / ENTITIES_FILE))
        issues.extend(_check_entities(entities))
    except ConfigError as error:
        issues.extend(error.issues)
    pipeline = None
    try:
        pipeline = load_pipeline(path)
    except ConfigError as error:
        issues.extend(error.issues)
    if issues or sources is None or topics is None or entities is None or pipeline is None:
        raise ConfigError(issues)
    return ConfigFiles(sources=sources, topics=topics, entities=entities, pipeline=pipeline)
