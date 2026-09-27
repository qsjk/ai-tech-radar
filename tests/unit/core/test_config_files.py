"""`config/` files: Sprint 1 schemas (IV §16.5; `schemas` part of T-CFG-02)."""

from datetime import timedelta
from pathlib import Path

import pytest

from app.core.config_files import WATCHDOG_TIMEOUT_MIN, ConfigError, ConfigIssue, load_config_files, load_pipeline
from app.ops.watchdog import REFRESH_INTERVAL

SOURCES = """\
sources:
  - key: blog-a
    name: Blog A
    type: rss
    url: https://a.example.com/feed.xml
  - key: repo-b
    name: Repo B
    type: github
    url: https://github.com/b/b
    poll_interval: 2h
    relevance: always
    config:
      repo: b/b
"""

TOPICS = """\
topics:
  - slug: parent
    name: Parent
    keywords: ["parent"]
  - slug: child
    name: Child
    parent: parent
    keywords:
      - { term: "child", weight: 3 }
      - { term: 'child(ren|hood)', regex: true }
    exclude: ["childish"]
"""

ENTITIES = """\
entities:
  - type: company
    canonical_name: acme
    name: Acme
  - type: model
    canonical_name: acme-one
    name: Acme One
    aliases: [{ term: 'acme[ -]?one', regex: true }]
github_reserved_paths: [orgs, topics]
"""


def write(directory: Path, **files: str | None) -> Path:
    """Valid `config/` directory; a file passed as `None` is left out, a string replaces it."""
    contents = {"sources.yaml": SOURCES, "topics.yaml": TOPICS, "entities.yaml": ENTITIES}
    for name, content in files.items():
        contents[f"{name}.yaml"] = content  # type: ignore[assignment]
    for name, content in contents.items():
        if content is not None:
            (directory / name).write_text(content, encoding="utf-8")
    return directory


def problems(directory: Path) -> list[ConfigIssue]:
    with pytest.raises(ConfigError) as info:
        load_config_files(directory)
    return info.value.issues


def test_valid_configuration_loaded(tmp_path: Path) -> None:
    config = load_config_files(write(tmp_path))
    assert [s.key for s in config.sources.sources] == ["blog-a", "repo-b"]
    assert config.sources.sources[1].poll_interval == timedelta(hours=2)
    assert config.topics.topics[1].keywords[1].regex
    assert config.entities.github_reserved_paths == ["orgs", "topics"]
    assert config.pipeline.ops.heartbeat_stale_after == timedelta(seconds=120)


@pytest.mark.spec("T-CFG-02:schemas")
def test_invalid_yaml_syntax(tmp_path: Path) -> None:
    (issue,) = problems(write(tmp_path, topics="topics:\n  - slug: [open\n"))
    assert issue.file == "topics.yaml"
    assert "invalid YAML syntax (line" in issue.message


@pytest.mark.spec("T-CFG-02:schemas")
def test_missing_required_field(tmp_path: Path) -> None:
    sources = SOURCES.replace("    url: https://github.com/b/b\n", "")
    (issue,) = problems(write(tmp_path, sources=sources))
    assert (issue.file, issue.key, issue.field) == ("sources.yaml", "repo-b", "url")
    assert str(issue) == "sources.yaml · entry 'repo-b' · field 'url': Field required"


@pytest.mark.spec("T-CFG-02:schemas")
@pytest.mark.parametrize(
    ("file", "content", "expected"),
    [
        ("sources", SOURCES.replace("key: repo-b", "key: blog-a"), ("sources.yaml", "blog-a", "key")),
        (
            "topics",
            TOPICS.replace("slug: child", "slug: parent").replace("    parent: parent\n", ""),
            ("topics.yaml", "parent", "slug"),
        ),
        (
            "entities",
            ENTITIES.replace("canonical_name: acme-one", "canonical_name: acme").replace(
                "type: model", "type: company"
            ),
            ("entities.yaml", "company:acme", "canonical_name"),
        ),
    ],
)
def test_duplicate_key(tmp_path: Path, file: str, content: str, expected: tuple[str, str, str]) -> None:
    (issue,) = problems(write(tmp_path, **{file: content}))
    assert (issue.file, issue.key, issue.field) == expected
    assert "duplicate" in issue.message


@pytest.mark.spec("T-CFG-02:schemas")
def test_missing_parent(tmp_path: Path) -> None:
    (issue,) = problems(write(tmp_path, topics=TOPICS.replace("parent: parent", "parent: absent")))
    assert (issue.file, issue.key, issue.field) == ("topics.yaml", "child", "parent")
    assert issue.message == "parent 'absent' does not exist"


@pytest.mark.spec("T-CFG-02:schemas")
def test_parent_cycle(tmp_path: Path) -> None:
    topics = TOPICS.replace("    name: Parent\n", "    name: Parent\n    parent: child\n")
    (issue,) = problems(write(tmp_path, topics=topics))
    assert (issue.file, issue.field) == ("topics.yaml", "parent")
    assert issue.message.startswith("parent cycle: ")
    assert "parent" in issue.message and "child" in issue.message


@pytest.mark.spec("T-CFG-02:schemas")
def test_invalid_regex_in_a_topic_and_an_alias(tmp_path: Path) -> None:
    topics = TOPICS.replace("child(ren|hood)", "child(ren|hood")
    entities = ENTITIES.replace("acme[ -]?one", "acme[ -?one")
    issues = problems(write(tmp_path, topics=topics, entities=entities))
    assert [(i.file, i.key, i.field) for i in issues] == [
        ("topics.yaml", "child", "keywords.1"),
        ("entities.yaml", "model:acme-one", "aliases.0"),
    ]
    assert all(i.message.startswith("invalid regex") for i in issues)


@pytest.mark.spec("T-CFG-02:schemas")
def test_key_repeated_in_the_same_mapping(tmp_path: Path) -> None:
    sources = SOURCES.replace("    name: Blog A\n", "    name: Blog A\n    name: Blog A bis\n")
    (issue,) = problems(write(tmp_path, sources=sources))
    assert issue.file == "sources.yaml"
    assert issue.message == "key 'name' repeated in the same mapping (line 4)"


@pytest.mark.spec("T-CFG-02:schemas")
def test_unknown_field_refused(tmp_path: Path) -> None:
    (issue,) = problems(write(tmp_path, sources=SOURCES.replace("    type: rss\n", "    type: rss\n    urll: x\n")))
    assert (issue.key, issue.field) == ("blog-a", "urll")


@pytest.mark.spec("T-CFG-02:schemas")
def test_every_problem_is_collected(tmp_path: Path) -> None:
    issues = problems(write(tmp_path, sources=None, topics=TOPICS.replace("parent: parent", "parent: absent")))
    assert [(i.file, i.message) for i in issues] == [
        ("sources.yaml", "required file missing"),
        ("topics.yaml", "parent 'absent' does not exist"),
    ]


def test_missing_pipeline_gives_the_defaults(tmp_path: Path) -> None:
    pipeline = load_pipeline(tmp_path)
    assert pipeline.ops.heartbeat_interval == timedelta(seconds=30)
    assert pipeline.ops.heartbeat_stale_after == timedelta(seconds=120)
    assert pipeline.ops.watchdog_timeout == timedelta(seconds=300)


def test_present_pipeline_read(tmp_path: Path) -> None:
    (tmp_path / "pipeline.yaml").write_text("ops:\n  heartbeat_stale_after: 3m\n", encoding="utf-8")
    assert load_pipeline(tmp_path).ops.heartbeat_stale_after == timedelta(minutes=3)


@pytest.mark.spec("T-CFG-02:schemas")
@pytest.mark.parametrize(
    ("content", "field"),
    [
        ("ops:\n  heartbeat_stale_after: soon\n", "heartbeat_stale_after"),
        ("ops:\n  heartbeat_stale_afer: 2m\n", "heartbeat_stale_afer"),
    ],
)
def test_invalid_pipeline_refused_with_the_same_format(tmp_path: Path, content: str, field: str) -> None:
    (tmp_path / "pipeline.yaml").write_text(content, encoding="utf-8")
    with pytest.raises(ConfigError) as info:
        load_pipeline(tmp_path)
    (issue,) = info.value.issues
    assert (issue.file, issue.key, issue.field) == ("pipeline.yaml", "ops", field)


@pytest.mark.spec("T-CFG-02:schemas")
@pytest.mark.parametrize("value", ["9s", "1s", "0s", 5])
def test_watchdog_timeout_below_the_minimum_refused(tmp_path: Path, value: str | int) -> None:
    (tmp_path / "pipeline.yaml").write_text(f"ops:\n  watchdog_timeout: {value}\n", encoding="utf-8")
    with pytest.raises(ConfigError) as info:
        load_pipeline(tmp_path)
    (issue,) = info.value.issues
    assert (issue.file, issue.key, issue.field) == ("pipeline.yaml", "ops", "watchdog_timeout")
    assert "at least 10s" in issue.message
    assert "watchdog refresh period" in issue.message


@pytest.mark.spec("T-CFG-02:schemas")
def test_watchdog_timeout_at_the_minimum_accepted(tmp_path: Path) -> None:
    (tmp_path / "pipeline.yaml").write_text("ops:\n  watchdog_timeout: 10s\n", encoding="utf-8")
    assert load_pipeline(tmp_path).ops.watchdog_timeout == timedelta(seconds=10)
    assert WATCHDOG_TIMEOUT_MIN == timedelta(seconds=2 * REFRESH_INTERVAL)


@pytest.mark.spec("T-CFG-01")
def test_repository_config_valid() -> None:
    config = load_config_files(Path(__file__).resolve().parents[3] / "config")
    assert {s.key for s in config.sources.sources} == {"claude-code-releases", "hn-mcp"}
    assert {t.slug for t in config.topics.topics} == {"anthropic", "claude-code", "mcp"}
    assert config.pipeline.ops.heartbeat_stale_after == timedelta(seconds=120)


@pytest.mark.spec("T-CFG-02:schemas")
def test_source_key_outside_the_pattern_refused(tmp_path: Path) -> None:
    (issue,) = problems(write(tmp_path, sources=SOURCES.replace("key: blog-a", "key: Blog_A")))
    assert (issue.file, issue.key, issue.field) == ("sources.yaml", "Blog_A", "key")
