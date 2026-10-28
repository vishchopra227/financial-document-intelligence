"""Financial metrics extraction engine for corporate reports and 10-K/10-Q filings."""

import re
import json
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from pathlib import Path

from backend.app.config import settings
from backend.app.db.models import Document, ExtractedMetric

logger = logging.getLogger("finsight.metrics")

# Key financial metrics with synonym patterns
METRIC_PATTERNS = [
    {
        "name": "Total Revenue",
        "synonyms": [r"total\s+revenue", r"net\s+sales", r"revenue", r"total\s+net\s+sales"],
        "unit": None,
        "is_percentage": False,
    },
    {
        "name": "Net Income",
        "synonyms": [r"net\s+income", r"net\s+earnings", r"net\s+profit", r"consolidated\s+net\s+income"],
        "unit": None,
        "is_percentage": False,
    },
    {
        "name": "Operating Income",
        "synonyms": [r"operating\s+income", r"operating\s+profit", r"operating\s+earnings"],
        "unit": None,
        "is_percentage": False,
    },
    {
        "name": "Operating Margin",
        "synonyms": [r"operating\s+margin", r"operating\s+income\s+margin"],
        "unit": "percentage",
        "is_percentage": True,
    },
    {
        "name": "Gross Margin",
        "synonyms": [r"gross\s+margin", r"gross\s+profit\s+margin"],
        "unit": "percentage",
        "is_percentage": True,
    },
    {
        "name": "Diluted EPS",
        "synonyms": [r"diluted\s+(?:earnings\s+per\s+share|eps)", r"diluted\s+net\s+income\s+per\s+share", r"earnings\s+per\s+share\s+-\s+diluted"],
        "unit": "USD/share",
        "is_percentage": False,
    },
    {
        "name": "Cash and Cash Equivalents",
        "synonyms": [r"cash\s+and\s+cash\s+equivalents", r"cash,\s+cash\s+equivalents", r"total\s+cash"],
        "unit": None,
        "is_percentage": False,
    },
    {
        "name": "Total Debt",
        "synonyms": [r"total\s+debt", r"term\s+debt", r"long-term\s+debt", r"total\s+borrowings"],
        "unit": None,
        "is_percentage": False,
    },
    {
        "name": "Total Assets",
        "synonyms": [r"total\s+assets"],
        "unit": None,
        "is_percentage": False,
    },
]


class FinancialMetricsExtractor:
    def __init__(self, db: Session):
        self.db = db

    def extract_and_store_metrics(self, document_id: str) -> List[ExtractedMetric]:
        """Extract structured metrics from document text and tables, then persist."""
        doc = self.db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError(f"Document '{document_id}' not found.")

        # Read extracted pages from cache
        cache_path = settings.UPLOAD_DIR / f"{document_id}_extracted.json"
        if not cache_path.exists():
            return []

        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        pages = data.get("pages", [])
        extracted: List[ExtractedMetric] = []
        table_metric_names = set()
        seen_metrics = set()

        # Step 1: Extract from Tables (Highest financial precision)
        for page in pages:
            page_num = page.get("page_number", 1)
            text = page.get("text", "")

            # Look for table sections
            tables = re.findall(r"\[TABLE START\](.*?)\[TABLE END\]", text, re.DOTALL)
            for table_text in tables:
                lines = [l.strip() for l in table_text.split("\n") if l.strip()]
                if not lines:
                    continue

                header_cells = [cell.strip() for cell in lines[0].split("|")]
                periods = [self._detect_period(cell) for cell in header_cells]

                for line in lines[1:]:
                    cells = [cell.strip() for cell in line.split("|")]
                    label = cells[0] if len(cells) > 1 else line
                    for target in METRIC_PATTERNS:
                        for syn in target["synonyms"]:
                            if not re.search(rf"\b{syn}\b", label, re.IGNORECASE):
                                continue

                            table_metric_names.add(target["name"])
                            value_cells = cells[1:] if len(cells) > 1 else [line]
                            for index, cell in enumerate(value_cells, start=1):
                                match = self._value_pattern().search(cell)
                                if not match:
                                    continue
                                period = (
                                    periods[index] if index < len(periods) else None
                                ) or doc.reporting_period
                                metric = self._make_metric(
                                    document_id, target, match, period, page_num,
                                    f"{lines[0]} | {line}"[:300], 0.95,
                                    header_cells[index] if index < len(header_cells) else None,
                                )
                                key = (metric.metric_name, metric.reporting_period, metric.page_number, metric.raw_value)
                                if key not in seen_metrics:
                                    extracted.append(metric)
                                    seen_metrics.add(key)
                            break

        # Step 2: Extract from Narrative Sentences
        for page in pages:
            page_num = page.get("page_number", 1)
            text = page.get("text", "")

            for target in METRIC_PATTERNS:
                if target["name"] in table_metric_names:
                    continue

                for syn in target["synonyms"]:
                    pattern = (
                        rf"\b{syn}\b[^\.\n]*?(?:was|of|reached|totaled|to)?\s*"
                        rf"(?P<value>{self._value_pattern().pattern})"
                    )
                    for match in re.finditer(pattern, text, re.IGNORECASE):
                        value_match = self._value_pattern().match(match.group("value"))
                        if not value_match:
                            continue
                        start = max(0, match.start() - 30)
                        end = min(len(text), match.end() + 70)
                        excerpt = text[start:end].replace("\n", " ").strip()
                        period = self._detect_period(excerpt) or doc.reporting_period
                        metric = self._make_metric(
                            document_id, target, value_match, period, page_num,
                            excerpt, 0.90,
                        )
                        key = (metric.metric_name, metric.reporting_period, metric.page_number, metric.raw_value)
                        if key not in seen_metrics:
                            extracted.append(metric)
                            seen_metrics.add(key)
                    if any(m.metric_name == target["name"] for m in extracted):
                        break

        # Step 3: Remove old metrics for this doc and persist fresh extractions
        self.db.query(ExtractedMetric).filter(ExtractedMetric.document_id == document_id).delete()
        for m in extracted:
            self.db.add(m)
        self.db.commit()

        logger.info("Extracted %s structured financial metrics for document %s", len(extracted), document_id)
        return extracted

    @staticmethod
    def _value_pattern() -> re.Pattern:
        return re.compile(
            r"(?P<currency>USD|EUR|GBP|[$€£])?\s*(?P<number>-?\(?\d[\d,]*(?:\.\d+)?\)?)"
            r"\s*(?P<scale>billion|million|thousand|B|M|K|%)?\s*(?P<currency_suffix>USD|EUR|GBP)?",
            re.IGNORECASE,
        )

    @staticmethod
    def _detect_period(text: str) -> Optional[str]:
        match = re.search(
            r"\b(FY\s*\d{2,4}|20\d{2}|Q[1-4]\s*(?:20\d{2}|\d{2})?)\b",
            text,
            re.IGNORECASE,
        )
        return re.sub(r"\s+", " ", match.group(0)).upper() if match else None

    def _make_metric(
        self, document_id: str, target: Dict[str, Any], match: re.Match,
        period: Optional[str], page_number: int, excerpt: str, confidence: float,
        column_header: Optional[str] = None,
    ) -> ExtractedMetric:
        currency_symbols = {
            "$": "USD", "€": "EUR", "£": "GBP",
            "USD": "USD", "EUR": "EUR", "GBP": "GBP",
        }
        symbol = match.group("currency") or match.group("currency_suffix")
        if not symbol and column_header:
            currency_match = re.search(r"\b(USD|EUR|GBP)\b|[$€£]", column_header, re.IGNORECASE)
            symbol = currency_match.group(0).upper() if currency_match else None
        scale = match.group("scale")
        if not scale and column_header:
            scale_match = re.search(r"\b(billions?|millions?|thousands?|B|M|K)\b", column_header, re.IGNORECASE)
            scale = scale_match.group(1) if scale_match else None
        unit = target["unit"]
        if scale:
            scale_name = scale.lower()
            unit = {
                "b": "billion", "billion": "billion", "billions": "billion",
                "m": "million", "million": "million", "millions": "million",
                "k": "thousand", "thousand": "thousand", "thousands": "thousand",
                "%": "percentage",
            }.get(scale_name, scale_name)
        elif target["is_percentage"]:
            unit = "percentage"
        elif target["name"] == "Diluted EPS":
            unit = "per share"

        raw_value = match.group(0).strip()
        return ExtractedMetric(
            document_id=document_id,
            metric_name=target["name"],
            raw_value=raw_value,
            numeric_value=self._parse_numeric(match.group("number")),
            unit=unit,
            currency=currency_symbols.get(symbol),
            reporting_period=period,
            page_number=page_number,
            source_excerpt=excerpt,
            confidence=confidence,
        )

    def _parse_numeric(self, val_str: str) -> Optional[float]:
        try:
            clean = val_str.replace(",", "").replace("(", "-").replace(")", "").strip()
            return float(clean)
        except Exception:
            return None

    def get_document_metrics(self, document_id: str) -> List[ExtractedMetric]:
        """Fetch stored metrics for a document, running extraction if not yet computed."""
        metrics = self.db.query(ExtractedMetric).filter(ExtractedMetric.document_id == document_id).all()
        if not metrics:
            metrics = self.extract_and_store_metrics(document_id)
        return metrics

    def compare_metrics(self, document_ids: List[str]) -> Dict[str, Any]:
        """Return comparative tabular representation of metrics across documents."""
        docs = self.db.query(Document).filter(Document.id.in_(document_ids)).all()
        doc_map = {d.id: d for d in docs}

        all_doc_metrics: Dict[str, List[ExtractedMetric]] = {}
        metric_periods = set()

        for doc_id in document_ids:
            metrics = self.get_document_metrics(doc_id)
            all_doc_metrics[doc_id] = metrics
            metric_periods.update((m.metric_name, m.reporting_period) for m in metrics)

        rows = []
        for m_name, period in sorted(metric_periods, key=lambda item: (item[0], item[1] or "")):
            row = {"metric_name": m_name, "reporting_period": period, "values": {}}
            for doc_id in document_ids:
                doc = doc_map.get(doc_id)
                evidence = [
                    {
                        "raw_value": metric.raw_value,
                        "numeric_value": metric.numeric_value,
                        "currency": metric.currency,
                        "unit": metric.unit,
                        "period": metric.reporting_period,
                        "page_number": metric.page_number,
                        "source_excerpt": metric.source_excerpt,
                        "confidence": metric.confidence,
                    }
                    for metric in all_doc_metrics.get(doc_id, [])
                    if metric.metric_name == m_name and metric.reporting_period == period
                ]
                primary = evidence[0] if evidence else {}
                row["values"][doc_id] = {
                    "document_name": doc.original_filename if doc else doc_id,
                    "raw_value": primary.get("raw_value", "N/A"),
                    "numeric_value": primary.get("numeric_value"),
                    "currency": primary.get("currency"),
                    "unit": primary.get("unit"),
                    "period": primary.get("period"),
                    "page_number": primary.get("page_number"),
                    "source_excerpt": primary.get("source_excerpt"),
                    "evidence": evidence,
                }
            rows.append(row)

        return {
            "document_ids": document_ids,
            "documents": [{"id": d.id, "filename": d.original_filename} for d in docs],
            "metrics_table": rows,
        }
