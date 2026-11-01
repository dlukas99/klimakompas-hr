from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import numpy as np
from rdflib import RDF
from rdflib.namespace import DCAT, DCTERMS

from klimakompas.core.config import Source
from klimakompas.pipeline.sensitivity import sensitivity
from klimakompas.quality.exports import DATASETS, EXPORT_FILES, ODBL, build_catalog
from klimakompas.quality.report import freshness_check, iso_duration, portal_check

NOW = datetime(2026, 11, 2, tzinfo=UTC)


def source(stale_after: str | None = "PT6H") -> Source:
    return Source.model_validate(
        {
            "id": "demo",
            "name": "Demo",
            "publisher": "P",
            "access": {},
            "format": "json",
            "license": "L",
            "attribution": "A",
            "used_for": [],
            "priority": "P0",
            "stale_after": stale_after,
            "verification": {"status": "verified", "date": "2026-11-01"},
        }
    )


def test_iso_duration() -> None:
    assert iso_duration("PT6H") == timedelta(hours=6)
    assert iso_duration("P3D") == timedelta(days=3)


def test_freshness() -> None:
    assert freshness_check(source(), NOW - timedelta(hours=2), NOW).passed
    assert not freshness_check(source(), NOW - timedelta(hours=7), NOW).passed
    assert not freshness_check(source(), None, NOW).passed


def test_portal_record_needs_a_licence_and_an_active_publisher() -> None:
    good = SimpleNamespace(organization="DGU", license_title="Otvorena dozvola")
    assert portal_check(source(), good).passed
    inactive = SimpleNamespace(organization="HAOP (NEAKTIVAN)", license_title=None)
    check = portal_check(source(), inactive)
    assert not check.passed
    assert check.details["publisher_active"] is False
    assert check.details["license_present"] is False


def test_identical_weights_on_one_hazard_rank_stays_the_same() -> None:
    # Hazards move together, so any weights give the same order.
    risks = np.column_stack([np.arange(30.0)] * 4)
    result = sensitivity(risks, np.full(4, 0.25), samples=20, alpha=1.0, top_n=5)
    assert result["median_spearman"] > 0.999
    assert result["stable_in_top"] == 5


def test_conflicting_hazards_lower_the_stability() -> None:
    risks = np.column_stack([np.arange(30.0), np.arange(30.0)[::-1]])
    result = sensitivity(risks, np.array([0.6, 0.4]), samples=200, alpha=1.0, top_n=5)
    assert result["p05_spearman"] < 0


def test_sensitivity_is_reproducible() -> None:
    risks = np.random.default_rng(1).random((40, 4))
    first = sensitivity(risks, np.full(4, 0.25), samples=30, alpha=1.0, top_n=5)
    assert first == sensitivity(risks, np.full(4, 0.25), samples=30, alpha=1.0, top_n=5)


def test_catalog_describes_every_dataset_with_licence_and_provenance() -> None:
    graph = build_catalog("https://example.test")
    datasets = list(graph.subjects(RDF.type, DCAT.Dataset))
    assert len(datasets) == len(DATASETS)
    for dataset in datasets:
        assert graph.value(dataset, DCTERMS.publisher) is not None
        assert graph.value(dataset, DCTERMS.spatial) is not None
        assert graph.value(dataset, DCAT.theme) is not None
        assert list(graph.objects(dataset, DCAT.distribution))
    for distribution in graph.subjects(RDF.type, DCAT.Distribution):
        assert str(graph.value(distribution, DCTERMS.license)) == ODBL
        assert str(graph.value(distribution, DCAT.accessURL)).startswith("https://example.test")


def test_export_names_are_a_closed_list() -> None:
    assert "ikr-jls.csv" in EXPORT_FILES
    assert "../.env" not in EXPORT_FILES
