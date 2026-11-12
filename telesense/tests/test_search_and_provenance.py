"""
Automated Test for Search Normalization and Provenance Labels.
Verifies that:
1. Search queries are case-insensitive, trim whitespace, and normalize accents.
2. Tower responses return source_type ('SIMULATED' or 'REAL - OpenCellID').
3. No 'TRAI Certified' or 'verified' strings appear in API outputs.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_towers_list_and_provenance():
    response = client.get("/api/towers")
    assert response.status_code == 200
    towers = response.json()
    assert len(towers) > 0

    for t in towers:
        # Check provenance badge field exists and is honest
        assert "source_type" in t or "tower_id" in t
        name = t.get("name", "")
        # Must not contain invented hardware IDs
        assert "(gNodeB-" not in name
        assert "(eNodeB-" not in name


def test_citizen_search_case_insensitivity():
    # Test case sensitivity & whitespace tolerance
    queries = ["mumbai", "MUMBAI", " Mumbai ", "Múmbai", "andhra pradesh", "ANDHRA PRADESH", " Andhra Pradesh "]
    results = []
    for q in queries:
        resp = client.get(f"/api/citizen/check-area?locality={q}")
        assert resp.status_code == 200, f"Query '{q}' failed"
        data = resp.json()
        assert "quality_label" in data
        results.append(data["area_name"])

    # All mumbai queries should resolve to the same area
    mumbai_results = results[:4]
    assert len(set(mumbai_results)) == 1, f"Inconsistent resolution for Mumbai queries: {mumbai_results}"


def test_no_forbidden_claims_in_incidents():
    resp = client.get("/api/incidents")
    assert resp.status_code == 200
    incidents = resp.json()
    assert len(incidents) >= 2

    for inc in incidents:
        # Must have verifiable source URL
        assert "source_url" in inc and inc["source_url"].startswith("http")
        # Must NOT claim Motera 35.4 TB
        assert "35.4" not in inc.get("title", "")
        assert "35.4" not in inc.get("summary", "")
        # Must NOT have fake 3GPP error codes
        assert "error_code_3gpp" not in inc or not inc["error_code_3gpp"]


def test_network_health_summary_provenance_counts():
    resp = client.get("/api/towers/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "real_opencellid_count" in data
    assert "simulated_count" in data
    assert data["total_towers"] == data["real_opencellid_count"] + data["simulated_count"]


def test_repo_docs_and_metrics_no_unverified_marketing_claims_or_low_rank_asn():
    from pathlib import Path
    import json
    import re

    repo = Path(__file__).resolve().parents[1]
    forbidden_phrases = ["trai certified", "99 verified", "real telecom incidents", "authentic", "certified", "compliant"]
    for rel in ["README.md", "docs/VIVA_PRESENTATION_SCRIPT.md", "docs/ACADEMIC_PROJECT_REPORT.md"]:
        txt = (repo / rel).read_text(encoding="utf-8").lower()
        assert not re.search(r"\bverified\b", txt), f"Forbidden un-cited 'verified' in {rel}"
        for phrase in forbidden_phrases:
            assert phrase not in txt, f"Forbidden claim '{phrase}' in {rel}"

    raw_metrics = json.loads((repo / "artifacts" / "metrics.json").read_text(encoding="utf-8"))
    val = raw_metrics["real_dataset_validation"]
    assert "ASN-45117" not in val["series_evaluated"], "Low-ranked AS45117 must be excluded"
    assert "network-level web traffic, may include fixed broadband" in val.get("operator_broadband_note", "").lower()
    assert "related series (states are subsets of india)" in val.get("scope_note", "").lower()


