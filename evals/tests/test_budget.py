import pytest

from runner.budget import Budget, BudgetExceeded, ModelPricing


def test_records_cost_under_cap():
    pricing = ModelPricing(input_per_mtok=3.0, output_per_mtok=15.0)
    b = Budget(cap_usd=1.00)
    b.charge("claude-sonnet-4-6", input_tokens=1000, output_tokens=500, pricing=pricing)
    assert b.spent_usd == pytest.approx(0.003 + 0.0075, abs=1e-6)


def test_aborts_when_cap_exceeded():
    pricing = ModelPricing(input_per_mtok=3.0, output_per_mtok=15.0)
    b = Budget(cap_usd=0.005)
    with pytest.raises(BudgetExceeded):
        b.charge("claude-sonnet-4-6", input_tokens=1000, output_tokens=500, pricing=pricing)


def test_check_before_spend_does_not_charge():
    pricing = ModelPricing(input_per_mtok=3.0, output_per_mtok=15.0)
    b = Budget(cap_usd=0.005)
    assert b.would_exceed(input_tokens=1000, output_tokens=500, pricing=pricing) is True
    assert b.spent_usd == 0
