import json

import pytest

from app.services.report_agent import Report, ReportManager, ReportStatus


@pytest.fixture(autouse=True)
def reports_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(ReportManager, "REPORTS_DIR", str(tmp_path))
    return tmp_path


def save_report(report_id, timestamp, status, simulation_id="sim_example"):
    report = Report(
        report_id=report_id,
        simulation_id=simulation_id,
        graph_id="graph_example",
        simulation_requirement="Scenario",
        status=status,
        created_at=timestamp,
    )
    ReportManager.save_report(report)
    return report


def test_regenerated_report_replaces_older_success_in_lookup(reports_dir, monkeypatch):
    original = save_report("report_original", "2026-10-01T12:00:00", ReportStatus.COMPLETED)
    newer = save_report("report_recovered", "2026-10-01T12:05:00", ReportStatus.COMPLETED)
    unrelated = save_report(
        "report_other", "2026-10-01T12:10:00", ReportStatus.COMPLETED, "sim_other"
    )

    # Directory enumeration order must not affect the visible revision.
    monkeypatch.setattr(
        "app.services.report_agent.os.listdir",
        lambda _: [original.report_id, unrelated.report_id, newer.report_id],
    )

    assert ReportManager.get_report_by_simulation("sim_example").report_id == newer.report_id
    assert ReportManager.get_report(original.report_id) == original


def test_incomplete_retry_keeps_last_success_and_reads_legacy_file(reports_dir, monkeypatch):
    original = save_report("report_original", "2026-10-01T12:00:00", ReportStatus.COMPLETED)
    retry = save_report("report_retry", "2026-10-01T12:05:00", ReportStatus.FAILED)
    legacy = reports_dir / "report_legacy.json"
    legacy.write_text(json.dumps(original.to_dict()), encoding="utf-8")
    (reports_dir / original.report_id / "meta.json").unlink()
    monkeypatch.setattr(
        "app.services.report_agent.os.listdir", lambda _: [retry.report_id, legacy.name]
    )

    assert ReportManager.get_report_by_simulation("sim_example").report_id == original.report_id


def test_without_success_returns_most_recent_attempt(monkeypatch):
    failed = save_report("report_failed", "2026-10-01T12:00:00", ReportStatus.FAILED)
    pending = save_report("report_pending", "2026-10-01T12:05:00", ReportStatus.PENDING)
    monkeypatch.setattr(
        "app.services.report_agent.os.listdir", lambda _: [failed.report_id, pending.report_id]
    )

    assert ReportManager.get_report_by_simulation("sim_example").report_id == pending.report_id
