"""Tests for the lead stuck-ness scoring algorithm."""

from datetime import date, timedelta

import pytest

from app.services.lead_intelligence.scorer import score_lead, priority_from_score


class TestScoreLead:
    def test_fresh_project_low_score(self):
        score = score_lead(
            days_in_status=30,
            status="under_verification",
            crediting_period_end=date.today() + timedelta(days=365),
            last_verification_date=date.today() - timedelta(days=30),
            methodology="VMR0006",
        )
        assert 0 <= score <= 30
        assert priority_from_score(score) == "low"

    def test_stuck_under_verification_high_score(self):
        score = score_lead(
            days_in_status=250,
            status="under_verification",
            crediting_period_end=date.today() + timedelta(days=200),
            last_verification_date=None,
            methodology="VM0050",
        )
        assert score >= 50
        assert priority_from_score(score) in ("high", "critical")

    def test_overdue_crediting_period_critical(self):
        score = score_lead(
            days_in_status=100,
            status="registered",
            crediting_period_end=date.today() - timedelta(days=10),
            last_verification_date=date.today() - timedelta(days=800),
            methodology="AMS-II.G",
        )
        assert score >= 55
        assert priority_from_score(score) in ("high", "critical")

    def test_long_verification_gap(self):
        score = score_lead(
            days_in_status=400,
            status="registered",
            crediting_period_end=date.today() + timedelta(days=500),
            last_verification_date=date.today() - timedelta(days=800),
            methodology="TPDDTEC_v4",
        )
        assert score >= 35

    def test_no_data_defaults(self):
        score = score_lead(
            days_in_status=None,
            status="unknown",
            crediting_period_end=None,
            last_verification_date=None,
            methodology=None,
        )
        assert 0 <= score <= 20

    def test_methodology_weights(self):
        vm0050 = score_lead(
            days_in_status=200,
            status="under_verification",
            crediting_period_end=date.today() + timedelta(days=300),
            last_verification_date=None,
            methodology="VM0050",
        )
        tpddtec = score_lead(
            days_in_status=200,
            status="under_verification",
            crediting_period_end=date.today() + timedelta(days=300),
            last_verification_date=None,
            methodology="TPDDTEC_v4",
        )
        assert vm0050 > tpddtec

    def test_max_score_capped_at_100(self):
        score = score_lead(
            days_in_status=1000,
            status="under_validation",
            crediting_period_end=date.today() - timedelta(days=5),
            last_verification_date=date.today() - timedelta(days=1000),
            methodology="VM0050",
        )
        assert score == 100.0


class TestPriorityFromScore:
    def test_critical(self):
        assert priority_from_score(80) == "critical"
        assert priority_from_score(100) == "critical"

    def test_high(self):
        assert priority_from_score(60) == "high"
        assert priority_from_score(75) == "high"

    def test_medium(self):
        assert priority_from_score(40) == "medium"
        assert priority_from_score(55) == "medium"

    def test_low(self):
        assert priority_from_score(0) == "low"
        assert priority_from_score(30) == "low"
