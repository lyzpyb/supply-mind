"""Tests for enterprise audit logging."""

import os
import shutil
import tempfile

import pytest

from supplymind.enterprise import (
    AuditEvent,
    AuditEventType,
    AuditLogger,
)


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


class TestAuditLogger:
    """Test audit log writing and querying."""

    def test_log_and_query(self, tmp_dir):
        al = AuditLogger(audit_dir=tmp_dir)
        al.log(AuditEvent(
            event_type=AuditEventType.SKILL_EXECUTION,
            skill="demand_forecast",
            action="execute",
            outcome="success",
        ))

        entries = al.query()
        assert len(entries) == 1
        assert entries[0]["skill"] == "demand_forecast"
        assert entries[0]["event_type"] == "skill_execution"

    def test_log_skill_execution(self, tmp_dir):
        al = AuditLogger(audit_dir=tmp_dir)
        al.log_skill_execution(
            skill="pricing_elasticity",
            arguments={"prices": [1, 2], "quantities": [10, 20]},
            outcome="success",
            duration_ms=42.5,
        )

        entries = al.query(event_type=AuditEventType.SKILL_EXECUTION)
        assert len(entries) == 1
        assert entries[0]["duration_ms"] == 42.5
        assert "prices" in entries[0]["detail"]["arguments_keys"]

    def test_log_hitl_decision(self, tmp_dir):
        al = AuditLogger(audit_dir=tmp_dir)
        al.log_hitl_decision(
            session_id="hitl_001",
            skill="demand_forecast",
            decision="approved",
            reason="Looks good",
            actor="analyst@company.com",
        )

        entries = al.query(event_type=AuditEventType.HITL_DECISION)
        assert len(entries) == 1
        assert entries[0]["actor"] == "analyst@company.com"
        assert entries[0]["session_id"] == "hitl_001"

    def test_log_pipeline_run(self, tmp_dir):
        al = AuditLogger(audit_dir=tmp_dir)
        al.log_pipeline_run(
            pipeline_name="retail-replenish",
            status="completed",
            steps_completed=5,
            total_steps=5,
            duration_ms=1234.5,
        )

        entries = al.query(event_type=AuditEventType.PIPELINE_RUN)
        assert len(entries) == 1
        assert entries[0]["detail"]["steps_completed"] == 5

    def test_log_data_access(self, tmp_dir):
        al = AuditLogger(audit_dir=tmp_dir)
        al.log_data_access("retail_grocery", actor="data_team")

        entries = al.query(event_type=AuditEventType.DATA_ACCESS)
        assert len(entries) == 1
        assert entries[0]["detail"]["dataset_id"] == "retail_grocery"

    def test_query_filter_by_skill(self, tmp_dir):
        al = AuditLogger(audit_dir=tmp_dir)
        al.log_skill_execution("demand_forecast", {}, "success")
        al.log_skill_execution("pricing_elasticity", {}, "success")
        al.log_skill_execution("demand_forecast", {}, "error")

        entries = al.query(skill="demand_forecast")
        assert len(entries) == 2

    def test_query_filter_by_actor(self, tmp_dir):
        al = AuditLogger(audit_dir=tmp_dir)
        al.log(AuditEvent(event_type=AuditEventType.SKILL_EXECUTION, actor="alice"))
        al.log(AuditEvent(event_type=AuditEventType.SKILL_EXECUTION, actor="bob"))

        entries = al.query(actor="alice")
        assert len(entries) == 1

    def test_query_limit(self, tmp_dir):
        al = AuditLogger(audit_dir=tmp_dir)
        for i in range(20):
            al.log_skill_execution(f"skill_{i}", {}, "success")

        entries = al.query(limit=5)
        assert len(entries) == 5

    def test_summary(self, tmp_dir):
        al = AuditLogger(audit_dir=tmp_dir)
        al.log_skill_execution("demand_forecast", {}, "success")
        al.log_skill_execution("demand_forecast", {}, "success")
        al.log_skill_execution("pricing_elasticity", {}, "error")
        al.log_hitl_decision("s1", "demand_forecast", "approved")

        summary = al.summary()
        assert summary["total_entries"] == 4
        assert summary["by_type"]["skill_execution"] == 3
        assert summary["by_type"]["hitl_decision"] == 1
        assert summary["by_outcome"]["success"] == 3

    def test_audit_event_auto_timestamp(self):
        event = AuditEvent(event_type=AuditEventType.SKILL_EXECUTION)
        assert event.timestamp.endswith("Z")
        assert "T" in event.timestamp

    def test_thread_safety(self, tmp_dir):
        import threading
        al = AuditLogger(audit_dir=tmp_dir)

        def write_entries():
            for i in range(50):
                al.log_skill_execution(f"skill_{i}", {}, "success")

        threads = [threading.Thread(target=write_entries) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        entries = al.query(limit=10000)
        assert len(entries) == 200
