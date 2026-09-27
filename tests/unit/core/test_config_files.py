"""Fichiers `config/` : schémas du Sprint 1 (IV §16.5 ; volet `schemas` de T-CFG-02)."""

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
    name: Dépôt B
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
  - slug: enfant
    name: Enfant
    parent: parent
    keywords:
      - { term: "enfant", weight: 3 }
      - { term: 'enf(ant|ance)', regex: true }
    exclude: ["enfantillage"]
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


def ecrire(dossier: Path, **fichiers: str | None) -> Path:
    """Dossier `config/` valide ; un fichier passé à `None` est omis, une chaîne le remplace."""
    contenus = {"sources.yaml": SOURCES, "topics.yaml": TOPICS, "entities.yaml": ENTITIES}
    for nom, contenu in fichiers.items():
        contenus[f"{nom}.yaml"] = contenu  # type: ignore[assignment]
    for nom, contenu in contenus.items():
        if contenu is not None:
            (dossier / nom).write_text(contenu, encoding="utf-8")
    return dossier


def probleme(dossier: Path) -> list[ConfigIssue]:
    with pytest.raises(ConfigError) as info:
        load_config_files(dossier)
    return info.value.issues


def test_configuration_valide_chargee(tmp_path: Path) -> None:
    config = load_config_files(ecrire(tmp_path))
    assert [s.key for s in config.sources.sources] == ["blog-a", "repo-b"]
    assert config.sources.sources[1].poll_interval == timedelta(hours=2)
    assert config.topics.topics[1].keywords[1].regex
    assert config.entities.github_reserved_paths == ["orgs", "topics"]
    assert config.pipeline.ops.heartbeat_stale_after == timedelta(seconds=120)


@pytest.mark.spec("T-CFG-02:schemas")
def test_syntaxe_yaml_invalide(tmp_path: Path) -> None:
    (issue,) = probleme(ecrire(tmp_path, topics="topics:\n  - slug: [ouvert\n"))
    assert issue.file == "topics.yaml"
    assert "invalid YAML syntax (line" in issue.message


@pytest.mark.spec("T-CFG-02:schemas")
def test_champ_obligatoire_manquant(tmp_path: Path) -> None:
    sources = SOURCES.replace("    url: https://github.com/b/b\n", "")
    (issue,) = probleme(ecrire(tmp_path, sources=sources))
    assert (issue.file, issue.key, issue.field) == ("sources.yaml", "repo-b", "url")
    assert str(issue) == "sources.yaml · entry 'repo-b' · field 'url': Field required"


@pytest.mark.spec("T-CFG-02:schemas")
@pytest.mark.parametrize(
    ("fichier", "contenu", "attendu"),
    [
        ("sources", SOURCES.replace("key: repo-b", "key: blog-a"), ("sources.yaml", "blog-a", "key")),
        (
            "topics",
            TOPICS.replace("slug: enfant", "slug: parent").replace("    parent: parent\n", ""),
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
def test_doublon_de_cle(tmp_path: Path, fichier: str, contenu: str, attendu: tuple[str, str, str]) -> None:
    (issue,) = probleme(ecrire(tmp_path, **{fichier: contenu}))
    assert (issue.file, issue.key, issue.field) == attendu
    assert "duplicate" in issue.message


@pytest.mark.spec("T-CFG-02:schemas")
def test_parent_inexistant(tmp_path: Path) -> None:
    (issue,) = probleme(ecrire(tmp_path, topics=TOPICS.replace("parent: parent", "parent: absent")))
    assert (issue.file, issue.key, issue.field) == ("topics.yaml", "enfant", "parent")
    assert issue.message == "parent 'absent' does not exist"


@pytest.mark.spec("T-CFG-02:schemas")
def test_cycle_de_parents(tmp_path: Path) -> None:
    topics = TOPICS.replace("    name: Parent\n", "    name: Parent\n    parent: enfant\n")
    (issue,) = probleme(ecrire(tmp_path, topics=topics))
    assert (issue.file, issue.field) == ("topics.yaml", "parent")
    assert issue.message.startswith("parent cycle: ")
    assert "parent" in issue.message and "enfant" in issue.message


@pytest.mark.spec("T-CFG-02:schemas")
def test_regex_invalide_dans_un_topic_et_un_alias(tmp_path: Path) -> None:
    topics = TOPICS.replace("enf(ant|ance)", "enf(ant|ance")
    entities = ENTITIES.replace("acme[ -]?one", "acme[ -?one")
    issues = probleme(ecrire(tmp_path, topics=topics, entities=entities))
    assert [(i.file, i.key, i.field) for i in issues] == [
        ("topics.yaml", "enfant", "keywords.1"),
        ("entities.yaml", "model:acme-one", "aliases.0"),
    ]
    assert all(i.message.startswith("invalid regex") for i in issues)


@pytest.mark.spec("T-CFG-02:schemas")
def test_cle_repetee_dans_un_meme_mappage(tmp_path: Path) -> None:
    sources = SOURCES.replace("    name: Blog A\n", "    name: Blog A\n    name: Blog A bis\n")
    (issue,) = probleme(ecrire(tmp_path, sources=sources))
    assert issue.file == "sources.yaml"
    assert issue.message == "key 'name' repeated in the same mapping (line 4)"


@pytest.mark.spec("T-CFG-02:schemas")
def test_champ_inconnu_refuse(tmp_path: Path) -> None:
    (issue,) = probleme(ecrire(tmp_path, sources=SOURCES.replace("    type: rss\n", "    type: rss\n    urll: x\n")))
    assert (issue.key, issue.field) == ("blog-a", "urll")


@pytest.mark.spec("T-CFG-02:schemas")
def test_tous_les_problemes_sont_rassembles(tmp_path: Path) -> None:
    issues = probleme(ecrire(tmp_path, sources=None, topics=TOPICS.replace("parent: parent", "parent: absent")))
    assert [(i.file, i.message) for i in issues] == [
        ("sources.yaml", "required file missing"),
        ("topics.yaml", "parent 'absent' does not exist"),
    ]


def test_pipeline_absent_donne_les_defauts(tmp_path: Path) -> None:
    pipeline = load_pipeline(tmp_path)
    assert pipeline.ops.heartbeat_interval == timedelta(seconds=30)
    assert pipeline.ops.heartbeat_stale_after == timedelta(seconds=120)
    assert pipeline.ops.watchdog_timeout == timedelta(seconds=300)


def test_pipeline_present_lu(tmp_path: Path) -> None:
    (tmp_path / "pipeline.yaml").write_text("ops:\n  heartbeat_stale_after: 3m\n", encoding="utf-8")
    assert load_pipeline(tmp_path).ops.heartbeat_stale_after == timedelta(minutes=3)


@pytest.mark.spec("T-CFG-02:schemas")
@pytest.mark.parametrize(
    ("contenu", "champ"),
    [
        ("ops:\n  heartbeat_stale_after: bientôt\n", "heartbeat_stale_after"),
        ("ops:\n  heartbeat_stale_afer: 2m\n", "heartbeat_stale_afer"),
    ],
)
def test_pipeline_invalide_refuse_avec_le_meme_format(tmp_path: Path, contenu: str, champ: str) -> None:
    (tmp_path / "pipeline.yaml").write_text(contenu, encoding="utf-8")
    with pytest.raises(ConfigError) as info:
        load_pipeline(tmp_path)
    (issue,) = info.value.issues
    assert (issue.file, issue.key, issue.field) == ("pipeline.yaml", "ops", champ)


@pytest.mark.spec("T-CFG-02:schemas")
@pytest.mark.parametrize("valeur", ["9s", "1s", "0s", 5])
def test_watchdog_timeout_sous_le_minimum_refuse(tmp_path: Path, valeur: str | int) -> None:
    (tmp_path / "pipeline.yaml").write_text(f"ops:\n  watchdog_timeout: {valeur}\n", encoding="utf-8")
    with pytest.raises(ConfigError) as info:
        load_pipeline(tmp_path)
    (issue,) = info.value.issues
    assert (issue.file, issue.key, issue.field) == ("pipeline.yaml", "ops", "watchdog_timeout")
    assert "at least 10s" in issue.message
    assert "watchdog refresh period" in issue.message


@pytest.mark.spec("T-CFG-02:schemas")
def test_watchdog_timeout_au_minimum_accepte(tmp_path: Path) -> None:
    (tmp_path / "pipeline.yaml").write_text("ops:\n  watchdog_timeout: 10s\n", encoding="utf-8")
    assert load_pipeline(tmp_path).ops.watchdog_timeout == timedelta(seconds=10)
    assert WATCHDOG_TIMEOUT_MIN == timedelta(seconds=2 * REFRESH_INTERVAL)


@pytest.mark.spec("T-CFG-01")
def test_config_du_depot_valide() -> None:
    config = load_config_files(Path(__file__).resolve().parents[3] / "config")
    assert {s.key for s in config.sources.sources} == {"claude-code-releases", "hn-mcp"}
    assert {t.slug for t in config.topics.topics} == {"anthropic", "claude-code", "mcp"}
    assert config.pipeline.ops.heartbeat_stale_after == timedelta(seconds=120)


@pytest.mark.spec("T-CFG-02:schemas")
def test_cle_de_source_hors_motif_refusee(tmp_path: Path) -> None:
    (issue,) = probleme(ecrire(tmp_path, sources=SOURCES.replace("key: blog-a", "key: Blog_A")))
    assert (issue.file, issue.key, issue.field) == ("sources.yaml", "Blog_A", "key")
