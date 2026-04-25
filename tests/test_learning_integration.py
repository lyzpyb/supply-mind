"""
Integration tests for the Learning Loop wiring (Step 2).

Tests that HITL → FeedbackCollector → LearningLoop → DomainMemory
and Pipeline → SkillEvolution are properly connected.
"""

import json
import os
import shutil
import tempfile

import pytest

from supplymind.hitl.engine import HTLEngine, HITLDecision
from supplymind.hitl.feedback import FeedbackCollector, FeedbackType
from supplymind.learning.loop import LearningLoop, Feedback, FeedbackType as LFT
from supplymind.learning.evolution import SkillEvolution
from supplymind.hitl.store import JSONFileStore


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


class TestHTLEngineFeedbackBridge:
    """Test that HTLEngine.resolve() feeds into FeedbackCollector → LearningLoop."""

    def test_adjusted_session_triggers_feedback(self, tmp_dir):
        fc = FeedbackCollector(storage_dir=os.path.join(tmp_dir, "feedback"))
        ll = LearningLoop()
        engine = HTLEngine(feedback_collector=fc, learning_loop=ll)

        session = engine.create_session(
            level="review",
            skill="demand-forecast",
            step_name="step_0",
            title="Review forecast",
            summary="Check demand forecast",
            detail_data={"predicted": 100},
        )

        engine.resolve(
            session.id,
            HITLDecision.ADJUSTED,
            reason="Too high",
            adjusted_data={"predicted": 80},
        )

        assert len(fc._records) == 1
        assert fc._records[0]["feedback_type"] == "implicit_adjust"
        assert fc._records[0]["skill"] == "demand-forecast"

    def test_rejected_session_triggers_feedback(self, tmp_dir):
        fc = FeedbackCollector(storage_dir=os.path.join(tmp_dir, "feedback"))
        ll = LearningLoop()
        engine = HTLEngine(feedback_collector=fc, learning_loop=ll)

        session = engine.create_session(
            level="review", skill="pricing-markdown", step_name="step_1",
        )
        engine.resolve(session.id, HITLDecision.REJECTED, reason="Bad suggestion")

        assert len(fc._records) == 1
        assert fc._records[0]["feedback_type"] == "implicit_reject"

    def test_approved_session_does_not_trigger_feedback(self, tmp_dir):
        fc = FeedbackCollector(storage_dir=os.path.join(tmp_dir, "feedback"))
        ll = LearningLoop()
        engine = HTLEngine(feedback_collector=fc, learning_loop=ll)

        session = engine.create_session(
            level="review", skill="demand-forecast", step_name="step_0",
        )
        engine.resolve(session.id, HITLDecision.APPROVED, reason="Looks good")

        assert len(fc._records) == 0

    def test_auto_level_auto_approves(self, tmp_dir):
        fc = FeedbackCollector(storage_dir=os.path.join(tmp_dir, "feedback"))
        engine = HTLEngine(feedback_collector=fc)

        session = engine.create_session(
            level="auto", skill="data-profiler", step_name="step_0",
        )
        assert session.status == HITLDecision.APPROVED
        assert len(fc._records) == 0

    def test_learning_callback_wired_automatically(self, tmp_dir):
        fc = FeedbackCollector(storage_dir=os.path.join(tmp_dir, "feedback"))
        ll = LearningLoop()
        HTLEngine(feedback_collector=fc, learning_loop=ll)

        assert fc._learning_callback is not None
        assert fc._learning_callback == ll.on_feedback


class TestFeedbackToLearningLoop:
    """Test FeedbackCollector → LearningLoop callback chain."""

    def test_learning_callback_invoked_on_record(self, tmp_dir):
        received = []

        fc = FeedbackCollector(storage_dir=os.path.join(tmp_dir, "feedback"))
        fc.set_learning_callback(lambda fb: received.append(fb))

        fc.record(
            session_id="test_session",
            feedback_type=FeedbackType.IMPLICIT_ADJUST,
            skill="demand-forecast",
            sku_id="SKU001",
            category="dairy",
            hitl_session_id="hitl_001",
            original_value=100.0,
            adjusted_value=80.0,
            comment="Over-forecasted",
        )

        assert len(received) == 1
        assert received[0].skill == "demand-forecast"
        assert received[0].sku_id == "SKU001"

    def test_learning_loop_processes_adjustment(self, tmp_dir):
        ll = LearningLoop()

        fb = Feedback(
            feedback_type=LFT.IMPLICIT_ADJUST,
            skill="demand-forecast",
            sku_id="SKU001",
            category="dairy",
            original_value=100.0,
            adjusted_value=80.0,
            reason="Over-forecasted",
        )

        event = ll.on_feedback(fb)
        assert event is not None
        assert len(ll._feedback_history) == 1


class TestSkillEvolutionRecording:
    """Test SkillEvolution record and query."""

    def test_record_and_query_best_method(self, tmp_dir):
        se = SkillEvolution(storage_dir=os.path.join(tmp_dir, "evolution"))

        se.record_execution("demand-forecast", "holt_winters", mape=8.5, category="dairy")
        se.record_execution("demand-forecast", "ema", mape=12.0, category="dairy")
        se.record_execution("demand-forecast", "holt_winters", mape=9.0, category="dairy")

        best = se.get_best_method("demand-forecast", "dairy")
        assert best == "holt_winters"

    def test_evolution_profile_persists(self, tmp_dir):
        se = SkillEvolution(storage_dir=os.path.join(tmp_dir, "evolution"))
        se.record_execution("demand-forecast", "ema", mape=10.0, category="snacks")

        se2 = SkillEvolution(storage_dir=os.path.join(tmp_dir, "evolution"))
        profile = se2.get_profile("demand-forecast")
        assert profile.total_executions == 1
        assert "ema" in profile.method_performance

    def test_evolution_summary(self, tmp_dir):
        se = SkillEvolution(storage_dir=os.path.join(tmp_dir, "evolution"))
        se.record_execution("demand-forecast", "holt_winters", mape=7.0, category="dairy")

        summary = se.get_evolution_summary("demand-forecast")
        assert summary["total_executions"] == 1
        assert "holt_winters" in summary["method_performance"]


class TestDemandForecastEvolutionQuery:
    """Test that DemandForecast queries SkillEvolution when method=auto."""

    def test_forecast_uses_evolution_method(self, tmp_dir):
        se = SkillEvolution(storage_dir=os.path.join(tmp_dir, "evolution"))
        se.record_execution("demand-forecast", "ema", mape=5.0, category="dairy")
        se.record_execution("demand-forecast", "holt_winters", mape=15.0, category="dairy")

        from supplymind.skills.demand.forecast.main import DemandForecast
        skill = DemandForecast(skill_evolution=se)

        import numpy as np
        values = np.array([100, 110, 105, 120, 115, 130, 125, 140, 135, 150])
        result = skill._forecast_single(values, "auto", 7, 0.95, category="dairy")

        assert result.method_used == "ema"

    def test_forecast_fallback_without_evolution(self):
        from supplymind.skills.demand.forecast.main import DemandForecast
        skill = DemandForecast()

        import numpy as np
        values = np.array([100, 110, 105, 120, 115, 130, 125, 140, 135, 150])
        result = skill._forecast_single(values, "auto", 7, 0.95)

        assert result.method_used is not None
        assert len(result.predicted) == 7


class TestHTLSessionPersistence:
    """Test HITL session persistence via JSONFileStore."""

    def test_session_persisted_on_create(self, tmp_dir):
        store = JSONFileStore(base_dir=os.path.join(tmp_dir, "hitl"))
        engine = HTLEngine(store=store)

        session = engine.create_session(
            level="review", skill="demand-forecast", step_name="step_0",
            title="Review forecast", summary="Check it",
        )

        loaded = store.load(session.id)
        assert loaded is not None
        assert loaded["skill"] == "demand-forecast"
        assert loaded["status"] == "pending"

    def test_session_updated_on_resolve(self, tmp_dir):
        store = JSONFileStore(base_dir=os.path.join(tmp_dir, "hitl"))
        engine = HTLEngine(store=store)

        session = engine.create_session(
            level="review", skill="pricing-markdown", step_name="step_1",
        )
        engine.resolve(session.id, HITLDecision.APPROVED, "Looks good")

        loaded = store.load(session.id)
        assert loaded["status"] == "approved"

    def test_pending_sessions_restored_on_init(self, tmp_dir):
        store_dir = os.path.join(tmp_dir, "hitl")
        store = JSONFileStore(base_dir=store_dir)
        engine1 = HTLEngine(store=store)

        s1 = engine1.create_session(
            level="review", skill="demand-forecast", step_name="step_0",
        )
        s2 = engine1.create_session(
            level="review", skill="pricing-markdown", step_name="step_1",
        )
        engine1.resolve(s2.id, HITLDecision.APPROVED, "OK")

        store2 = JSONFileStore(base_dir=store_dir)
        engine2 = HTLEngine(store=store2)

        pending = engine2.get_pending_sessions()
        assert len(pending) == 1
        assert pending[0].id == s1.id
        assert pending[0].skill == "demand-forecast"

    def test_store_save_and_load(self, tmp_dir):
        store = JSONFileStore(base_dir=os.path.join(tmp_dir, "hitl"))
        store.save("test_123", {"id": "test_123", "skill": "test", "status": "pending"})

        loaded = store.load("test_123")
        assert loaded["skill"] == "test"

    def test_store_delete(self, tmp_dir):
        store = JSONFileStore(base_dir=os.path.join(tmp_dir, "hitl"))
        store.save("test_456", {"id": "test_456", "status": "pending"})
        store.delete("test_456")

        assert store.load("test_456") is None

