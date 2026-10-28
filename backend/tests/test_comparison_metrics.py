"""Automated tests for Phase 5: Multi-Document Comparison and Metrics Extraction."""

import csv
import json
import pytest
from backend.app.services.ai.llm import MockLLMAdapter


@pytest.fixture(autouse=True)
def mock_comparison_llm(monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.rag.comparison_service.get_llm_adapter",
        lambda: MockLLMAdapter(),
    )


def test_financial_metrics_extraction(client):
    """Test automated extraction of structured metrics from narrative text and tables."""
    report_content = (
        "ALPHABET INC. FORM 10-K EXCERPT\n\n"
        "[TABLE START]\n"
        "Financial Indicator | FY 2023 | FY 2022\n"
        "Total Revenue | $307.39B | $282.84B\n"
        "Operating Income | $84.29B | $74.84B\n"
        "Net Income | $73.80B | $59.97B\n"
        "[TABLE END]\n\n"
        "Management notes that Operating Margin was 27.4% for fiscal year 2023.\n"
        "Diluted EPS reached $5.80 per share.\n"
    ).encode("utf-8")

    files = {"file": ("alphabet_fy23.txt", report_content, "text/plain")}
    res = client.post("/api/documents/upload", files=files)
    assert res.status_code == 201
    doc_id = res.json()["id"]

    try:
        # Fetch extracted metrics
        metrics_res = client.get(f"/api/metrics/document/{doc_id}")
        assert metrics_res.status_code == 200
        data = metrics_res.json()
        assert data["document_id"] == doc_id
        metrics = data["metrics"]
        assert len(metrics) >= 3

        metric_names = [m["metric_name"] for m in metrics]
        assert "Total Revenue" in metric_names
        assert "Net Income" in metric_names

        rev_metric = next(m for m in metrics if m["metric_name"] == "Total Revenue")
        assert "$307.39B" in rev_metric["raw_value"]
        assert rev_metric["page_number"] == 1
        assert rev_metric["confidence"] >= 0.90

        # Export tests
        json_export = client.get(f"/api/metrics/document/{doc_id}/export?format=json")
        assert json_export.status_code == 200
        assert "attachment" in json_export.headers["content-disposition"]
        export_data = json.loads(json_export.text)
        assert export_data["document_id"] == doc_id

        csv_export = client.get(f"/api/metrics/document/{doc_id}/export?format=csv")
        assert csv_export.status_code == 200
        assert "attachment" in csv_export.headers["content-disposition"]
        assert "Total Revenue" in csv_export.text

    finally:
        client.delete(f"/api/documents/{doc_id}")


def test_multi_document_comparison(client):
    """Test comparative analysis across two separate annual reports."""
    doc1_content = (
        "COMPANY ALPHA REPORT 2023\n\n"
        "Total revenue was $100.0 billion.\n"
        "Net income was $20.0 billion.\n"
        "Operating margin was 25.0%.\n"
    ).encode("utf-8")

    doc2_content = (
        "COMPANY BETA REPORT 2023\n\n"
        "Total revenue was $150.0 billion.\n"
        "Net income was $15.0 billion.\n"
        "Operating margin was 12.0%.\n"
    ).encode("utf-8")

    r1 = client.post("/api/documents/upload", files={"file": ("=alpha_2023.txt", doc1_content, "text/plain")})
    r2 = client.post("/api/documents/upload", files={"file": ("beta_2023.txt", doc2_content, "text/plain")})
    id1, id2 = r1.json()["id"], r2.json()["id"]

    try:
        # Comparison Query
        compare_payload = {
            "document_ids": [id1, id2],
            "query": "Compare the total revenue and operating margin between Company Alpha and Company Beta.",
            "top_k_per_doc": 2,
        }
        comp_res = client.post("/api/compare", json=compare_payload)
        assert comp_res.status_code == 200
        comp_data = comp_res.json()

        assert len(comp_data["documents"]) == 2
        doc_names = [d["filename"] for d in comp_data["documents"]]
        assert "=alpha_2023.txt" in doc_names
        assert "beta_2023.txt" in doc_names

        assert len(comp_data["analysis"]) > 20
        assert comp_data["has_sufficient_evidence"] is True
        assert len(comp_data["citations"]) >= 2

        # Check citations point to both documents
        cited_docs = {c["document_id"] for c in comp_data["citations"]}
        assert id1 in cited_docs
        assert id2 in cited_docs

        # Compare metrics table endpoint
        table_res = client.get(f"/api/compare/metrics?document_ids={id1},{id2}")
        assert table_res.status_code == 200
        table_data = table_res.json()
        assert len(table_data["metrics_table"]) >= 1

        # Comparison Export Endpoints
        csv_export = client.post(
            "/api/compare/export?format=csv",
            json=compare_payload,
        )
        assert csv_export.status_code == 200
        assert "FINSIGHT INTELLIGENCE" in csv_export.text
        assert "alpha_2023.txt" in csv_export.text
        comparison_rows = list(csv.reader(csv_export.text.splitlines()))
        assert any(
            cell.startswith("'=alpha_2023.txt")
            for row in comparison_rows
            for cell in row
        )

        json_export = client.post(
            "/api/compare/export?format=json",
            json=compare_payload,
        )
        assert json_export.status_code == 200
        export_data = json_export.json()
        assert "synthesis_analysis" in export_data
        assert export_data["has_sufficient_evidence"] is True
        assert "evidence" in export_data["metrics_comparison_table"][0]["values"][id1]

    finally:
        client.delete(f"/api/documents/{id1}")
        client.delete(f"/api/documents/{id2}")


def test_comparison_validation_errors(client):
    """Test validation errors for comparison with < 2 documents or invalid IDs."""
    # Fewer than 2 docs
    res = client.post("/api/compare", json={"document_ids": ["single-doc-1"], "query": "compare"})
    assert res.status_code == 422  # Pydantic min_length=2 validation

    # Nonexistent docs
    res = client.post(
        "/api/compare",
        json={"document_ids": ["doc-nonexistent-1", "doc-nonexistent-2"], "query": "compare"},
    )
    assert res.status_code == 404


def test_metric_periods_currency_units_and_csv_safety(client):
    content = (
        "[TABLE START]\n"
        "Metric | FY 2023 | FY 2022\n"
        "Total Revenue | $307.39B | $282.84B\n"
        "Net Income | €12.5 million | £8.2 million\n"
        "Operating Income | 42 | 39\n"
        "[TABLE END]\n"
    ).encode("utf-8")
    response = client.post(
        "/api/documents/upload",
        files={"file": ("periods.txt", content, "text/plain")},
    )
    assert response.status_code == 201
    document_id = response.json()["id"]

    try:
        metrics_response = client.get(f"/api/metrics/document/{document_id}")
        assert metrics_response.status_code == 200
        metrics = metrics_response.json()["metrics"]

        revenue = [metric for metric in metrics if metric["metric_name"] == "Total Revenue"]
        assert [(metric["raw_value"], metric["reporting_period"]) for metric in revenue] == [
            ("$307.39B", "FY 2023"),
            ("$282.84B", "FY 2022"),
        ]
        assert [metric["unit"] for metric in revenue] == ["billion", "billion"]
        assert [metric["currency"] for metric in revenue] == ["USD", "USD"]

        net_income = [metric for metric in metrics if metric["metric_name"] == "Net Income"]
        assert [metric["currency"] for metric in net_income] == ["EUR", "GBP"]
        assert [metric["unit"] for metric in net_income] == ["million", "million"]
        assert [metric["raw_value"] for metric in net_income] == ["€12.5 million", "£8.2 million"]

        operating_income = next(metric for metric in metrics if metric["metric_name"] == "Operating Income")
        assert operating_income["currency"] is None
        assert operating_income["unit"] is None
        assert operating_income["source_excerpt"]

        csv_response = client.get(f"/api/metrics/document/{document_id}/export?format=csv")
        assert csv_response.status_code == 200
        rows = list(csv.reader(csv_response.text.splitlines()))
        assert any(row[0] == "Total Revenue" and row[5] == "FY 2023" for row in rows[1:])
        assert any(row[0] == "Total Revenue" and row[5] == "FY 2022" for row in rows[1:])
        json_response = client.get(f"/api/metrics/document/{document_id}/export?format=json")
        exported_metrics = json_response.json()["metrics"]
        assert all("reporting_period" in metric and "source_excerpt" in metric for metric in exported_metrics)
        assert all("confidence" in metric for metric in exported_metrics)

        injection_response = client.post(
            "/api/documents/upload",
            files={"file": ("untrusted.txt", b"=1+1 Gross Margin was 4%.", "text/plain")},
        )
        injection_id = injection_response.json()["id"]
        injection_csv = client.get(f"/api/metrics/document/{injection_id}/export?format=csv")
        injection_rows = list(csv.reader(injection_csv.text.splitlines()))
        assert any(row[-1].startswith("'=1+1") for row in injection_rows)
        client.delete(f"/api/documents/{injection_id}")
    finally:
        client.delete(f"/api/documents/{document_id}")


def test_metrics_comparison_keeps_reporting_period_and_evidence(client):
    content_a = b"[TABLE START]\nMetric | FY 2023 | FY 2022\nTotal Revenue | $10B | $8B\n[TABLE END]"
    content_b = b"[TABLE START]\nMetric | FY 2023\nTotal Revenue | EUR 14 million\n[TABLE END]"
    first = client.post("/api/documents/upload", files={"file": ("a.txt", content_a, "text/plain")})
    second = client.post("/api/documents/upload", files={"file": ("b.txt", content_b, "text/plain")})
    first_id, second_id = first.json()["id"], second.json()["id"]

    try:
        response = client.get(f"/api/compare/metrics?document_ids={first_id},{second_id}")
        assert response.status_code == 200
        rows = response.json()["metrics_table"]
        periods = {row["reporting_period"] for row in rows}
        assert periods == {"FY 2023", "FY 2022"}

        fy23 = next(row for row in rows if row["reporting_period"] == "FY 2023")
        assert fy23["values"][first_id]["evidence"][0]["page_number"] == 1
        assert fy23["values"][first_id]["evidence"][0]["source_excerpt"]
        assert fy23["values"][second_id]["currency"] == "EUR"
        assert fy23["values"][second_id]["unit"] == "million"
        assert fy23["values"][second_id]["evidence"][0]["raw_value"] == "EUR 14 million"
        fy22 = next(row for row in rows if row["reporting_period"] == "FY 2022")
        assert fy22["values"][second_id]["raw_value"] == "N/A"
    finally:
        client.delete(f"/api/documents/{first_id}")
        client.delete(f"/api/documents/{second_id}")


def test_metric_uses_currency_and_scale_from_table_header(client):
    content = b"[TABLE START]\nMetric | FY 2023 (EUR in millions)\nTotal Revenue | 12.5\n[TABLE END]"
    response = client.post(
        "/api/documents/upload",
        files={"file": ("header_units.txt", content, "text/plain")},
    )
    document_id = response.json()["id"]

    try:
        metrics = client.get(f"/api/metrics/document/{document_id}").json()["metrics"]
        revenue = next(metric for metric in metrics if metric["metric_name"] == "Total Revenue")
        assert revenue["raw_value"] == "12.5"
        assert revenue["numeric_value"] == 12.5
        assert revenue["currency"] == "EUR"
        assert revenue["unit"] == "million"
        assert revenue["reporting_period"] == "FY 2023"
        assert "EUR in millions" in revenue["source_excerpt"]
    finally:
        client.delete(f"/api/documents/{document_id}")
