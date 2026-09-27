"""Fichiers de configuration fonctionnelle `config/` (IV §16, docs/architecture.md §3.2).

- `load_config_files(path)` charge les quatre fichiers : pour le worker et `validate-config`.
- `load_pipeline(path)` charge `pipeline.yaml` seul, en lecture seule : pour l'app (E17).
- Toute erreur lève `ConfigError`, qui liste chaque problème avec **fichier, clé et champ** (IV §16.5).

Schémas du Sprint 1 (volet `schemas` de T-CFG-02). Le type de source, `poll_interval` et `config` restent des champs
libres jusqu'au registre des collectors (Sprint 2). `pipeline.yaml` ne déclare que les sections utiles au Sprint 1 ;
les autres arrivent avec leur étage (E6).
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

SLUG = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"

# ── Erreurs ───────────────────────────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ConfigIssue:
    """Un problème de configuration : fichier, entrée (clé), champ, message."""

    file: str
    key: str | None
    field: str | None
    message: str

    def __str__(self) -> str:
        parts = [self.file]
        if self.key is not None:
            parts.append(f"entrée « {self.key} »")
        if self.field is not None:
            parts.append(f"champ « {self.field} »")
        return " · ".join(parts) + f" : {self.message}"


class ConfigError(Exception):
    """Configuration invalide : un ou plusieurs problèmes, chacun avec fichier, clé et champ."""

    def __init__(self, issues: Iterable[ConfigIssue]) -> None:
        self.issues = list(issues)
        super().__init__("\n".join(str(issue) for issue in self.issues))


# ── Lecture YAML sûre, clés dupliquées refusées ───────────────────────────────────────────────────────────────────


class _DuplicateKeyError(yaml.YAMLError):
    pass


class _StrictLoader(yaml.SafeLoader):
    """Chargeur sûr qui refuse une clé répétée dans un même mappage (PyYAML garde sinon la dernière, en silence)."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Hashable, Any]:
        seen: set[Any] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                mark = key_node.start_mark
                raise _DuplicateKeyError(f"clé « {key} » répétée dans un même mappage (ligne {mark.line + 1})")
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def _read_yaml(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError([ConfigIssue(path.name, None, None, "fichier obligatoire absent")]) from None
    try:
        return yaml.load(text, Loader=_StrictLoader)  # noqa: S506 — chargeur dérivé de SafeLoader
    except _DuplicateKeyError as error:
        raise ConfigError([ConfigIssue(path.name, None, None, str(error))]) from None
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        where = f" (ligne {mark.line + 1}, colonne {mark.column + 1})" if mark is not None else ""
        problem = getattr(error, "problem", None) or str(error)
        raise ConfigError([ConfigIssue(path.name, None, None, f"syntaxe YAML invalide{where} : {problem}")]) from None


# ── Types communs ─────────────────────────────────────────────────────────────────────────────────────────────────

_DURATION = re.compile(r"^\s*(\d+)\s*(s|m|h|d)\s*$")
_UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}


def _parse_duration(value: Any) -> Any:
    """Durée écrite comme dans la spec (`120s`, `15m`, `2h`, `30d`), ou un entier de secondes."""
    if isinstance(value, bool):
        raise ValueError("durée attendue, par exemple 120s, 15m ou 2h")
    if isinstance(value, int):
        return timedelta(seconds=value)
    if isinstance(value, str):
        match = _DURATION.match(value)
        if match:
            return timedelta(**{_UNITS[match.group(2)]: int(match.group(1))})
    if isinstance(value, timedelta):
        return value
    raise ValueError("durée attendue, par exemple 120s, 15m ou 2h")


Duration = Annotated[timedelta, BeforeValidator(_parse_duration)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Keyword(_Model):
    """Terme de matching : chaîne, ou `{term, weight, regex}` (IV §16.3)."""

    term: str = Field(min_length=1)
    weight: float = Field(default=1, gt=0)
    regex: bool = False

    @model_validator(mode="after")
    def _compile_regex(self) -> Self:
        if self.regex:
            try:
                re.compile(self.term)
            except re.error as error:
                raise ValueError(f"regex invalide « {self.term} » : {error}") from None
        return self


def _keyword(value: Any) -> Any:
    return {"term": value} if isinstance(value, str) else value


KeywordEntry = Annotated[Keyword, BeforeValidator(_keyword)]

# ── Fichiers ──────────────────────────────────────────────────────────────────────────────────────────────────────


class SourceSpec(_Model):
    """Entrée de `sources.yaml` (IV §16.2)."""

    key: str = Field(pattern=SLUG)
    name: str = Field(min_length=1)
    type: str = Field(min_length=1)  # contrôlé par le registre des collectors au Sprint 2
    url: str = Field(min_length=1)
    enabled: bool = True
    poll_interval: Duration | None = None  # minimum du type contrôlé au Sprint 2
    relevance: Literal["filter", "always"] = "filter"
    extract: Literal["auto", "never"] | None = None
    config: dict[str, Any] = Field(default_factory=dict)  # validé par le collector au Sprint 2


class SourcesFile(_Model):
    sources: list[SourceSpec]


class TopicSpec(_Model):
    """Entrée de `topics.yaml` (IV §16.3)."""

    slug: str = Field(pattern=SLUG)
    name: str = Field(min_length=1)
    description: str | None = None
    parent: str | None = None
    enabled: bool = True
    keywords: list[KeywordEntry] = Field(min_length=1)
    exclude: list[str] = Field(default_factory=list)


class TopicsFile(_Model):
    topics: list[TopicSpec]


class EntitySpec(_Model):
    """Entrée de `entities.yaml` (IV §16.4)."""

    type: Literal["company", "product", "person", "project", "technology", "model", "repository"]
    canonical_name: str = Field(min_length=1)
    name: str = Field(min_length=1)
    aliases: list[KeywordEntry] = Field(default_factory=list)

    @field_validator("canonical_name")
    @classmethod
    def _lowercase(cls, value: str) -> str:
        if value != value.lower():
            raise ValueError("canonical_name doit être en minuscules")
        return value


class EntitiesFile(_Model):
    entities: list[EntitySpec]
    github_reserved_paths: list[str] = Field(default_factory=list)


class OpsSettings(_Model):
    """Section `ops` de `pipeline.yaml`, réglages utiles au Sprint 1 (VII §39.7)."""

    heartbeat_interval: Duration = timedelta(seconds=30)
    heartbeat_stale_after: Duration = timedelta(seconds=120)
    watchdog_timeout: Duration = timedelta(seconds=300)


class PipelineConfig(_Model):
    """`pipeline.yaml` : optionnel, absent → défauts (IV §16.5). Sections ajoutées sprint par sprint (E6)."""

    ops: OpsSettings = Field(default_factory=OpsSettings)


@dataclass(frozen=True)
class ConfigFiles:
    sources: SourcesFile
    topics: TopicsFile
    entities: EntitiesFile
    pipeline: PipelineConfig


# ── Validation ────────────────────────────────────────────────────────────────────────────────────────────────────


def _entry_key(file: str, data: Any, loc: tuple[int | str, ...]) -> tuple[str | None, str | None]:
    """Traduit l'emplacement Pydantic en (clé de l'entrée, champ)."""
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
        ConfigIssue(SOURCES_FILE, key, "key", "clé en double")
        for key in _duplicates(source.key for source in sources.sources)
    ]


def _check_topics(topics: TopicsFile) -> list[ConfigIssue]:
    issues = [
        ConfigIssue(TOPICS_FILE, slug, "slug", "slug en double") for slug in _duplicates(t.slug for t in topics.topics)
    ]
    parents = {topic.slug: topic.parent for topic in topics.topics}
    for topic in topics.topics:
        if topic.parent is not None and topic.parent not in parents:
            issues.append(ConfigIssue(TOPICS_FILE, topic.slug, "parent", f"parent « {topic.parent} » inexistant"))
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
                issues.append(ConfigIssue(TOPICS_FILE, current, "parent", f"cycle de parents : {chain}"))
    return issues


def _check_entities(entities: EntitiesFile) -> list[ConfigIssue]:
    keys = (f"{entity.type}:{entity.canonical_name}" for entity in entities.entities)
    return [
        ConfigIssue(ENTITIES_FILE, key, "canonical_name", "(type, canonical_name) en double")
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
    """Charge `pipeline.yaml` du dossier `path` ; absent → défauts."""
    file = path / PIPELINE_FILE
    if not file.exists():
        return PipelineConfig()
    return _validate(PipelineConfig, PIPELINE_FILE, _read_yaml(file))


def load_config_files(path: Path) -> ConfigFiles:
    """Charge et valide les quatre fichiers du dossier `path`. Rassemble tous les problèmes avant de lever."""
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
