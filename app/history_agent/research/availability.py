"""Shared read-time corpus availability checks for stored research evidence."""

from __future__ import annotations


def available_document_sql(document_id: str) -> str:
    """Return an SQL predicate for an internal document-id column expression.

    Corpus scans retain historical records when a PDF disappears. Only enabled
    documents with a present current file may support user-facing research.
    """

    return f"""EXISTS (
        SELECT 1 FROM documents available_d
        JOIN document_files available_f
          ON available_f.document_id = available_d.document_id
        WHERE available_d.document_id = {document_id}
          AND available_d.enabled = 1
          AND available_f.is_current = 1 AND available_f.is_present = 1
    )"""


def available_event_sql(alias: str, *, canonical: bool) -> str:
    """Hide unsupported events without altering their stored review decisions.

    A canonical description and its participants may combine every source. If
    any source is withdrawn, expose the surviving source events instead of a
    partially unsupported merged record. The timeline uses this same predicate
    both to select canonical events and to suppress their source events.
    """

    table = "canonical_event_evidence" if canonical else "event_evidence"
    key = "canonical_event_id" if canonical else "event_id"
    evidence = f"""FROM {table} available_ee
        JOIN evidence_records available_er
          ON available_er.evidence_id = available_ee.evidence_id
        WHERE available_ee.{key} = {alias}.{key}"""
    document = available_document_sql("available_er.document_id")
    supported = f"EXISTS (SELECT 1 {evidence} AND {document})"
    if canonical:
        return f"{supported} AND NOT EXISTS (SELECT 1 {evidence} AND NOT {document})"
    return supported
