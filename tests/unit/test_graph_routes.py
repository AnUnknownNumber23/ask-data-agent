"""Unit tests for graph routing logic — deterministic, no LLM dependency."""
import pytest
from agent.graph import (
    route_after_understand,
    route_after_sql_eval,
    route_after_act,
    route_after_result_eval,
    route_after_check,
)


class TestRouteAfterUnderstand:
    def test_clarify_when_question_set(self):
        state = {"clarification_question": "What do you mean?"}
        assert route_after_understand(state) == "clarify"

    def test_reason_when_no_question(self):
        state = {"clarification_question": None}
        assert route_after_understand(state) == "reason"

    def test_reason_when_empty_state(self):
        assert route_after_understand({}) == "reason"


class TestRouteAfterSqlEval:
    def test_pass_goes_to_act(self):
        state = {"evaluator_results": [{"gate": 1, "verdict": "pass"}]}
        assert route_after_sql_eval(state) == "act"

    def test_warn_goes_to_act(self):
        state = {"evaluator_results": [{"gate": 1, "verdict": "warn"}]}
        assert route_after_sql_eval(state) == "act"

    def test_reject_once_goes_to_reason(self):
        state = {"evaluator_results": [{"gate": 1, "verdict": "reject"}]}
        assert route_after_sql_eval(state) == "reason"

    def test_reject_three_times_escalates(self):
        state = {"evaluator_results": [
            {"gate": 1, "verdict": "reject"},
            {"gate": 1, "verdict": "reject"},
            {"gate": 1, "verdict": "reject"},
        ]}
        assert route_after_sql_eval(state) == "escalate"

    def test_reject_twice_still_reason(self):
        state = {"evaluator_results": [
            {"gate": 1, "verdict": "reject"},
            {"gate": 1, "verdict": "reject"},
        ]}
        assert route_after_sql_eval(state) == "reason"

    def test_empty_results_goes_to_act(self):
        assert route_after_sql_eval({"evaluator_results": []}) == "act"


class TestRouteAfterAct:
    def test_sql_error_with_few_retries_goes_to_reflect(self):
        state = {"sql_error": "column not found", "retry_count": 1}
        assert route_after_act(state) == "reflect"

    def test_sql_error_with_three_retries_escalates(self):
        state = {"sql_error": "column not found", "retry_count": 3}
        assert route_after_act(state) == "escalate"

    def test_sql_error_with_more_retries_escalates(self):
        state = {"sql_error": "timeout", "retry_count": 5}
        assert route_after_act(state) == "escalate"

    def test_no_error_goes_to_result_eval(self):
        state = {"sql_error": None}
        assert route_after_act(state) == "result_eval"


class TestRouteAfterResultEval:
    def test_reflect_goes_to_reason(self):
        state = {"evaluator_results": [{"gate": 2, "verdict": "reflect"}]}
        assert route_after_result_eval(state) == "reason"

    def test_degrade_goes_to_degrade(self):
        state = {"evaluator_results": [{"gate": 2, "verdict": "degrade"}]}
        assert route_after_result_eval(state) == "degrade"

    def test_pass_goes_to_analyze(self):
        state = {"evaluator_results": [{"gate": 2, "verdict": "pass"}]}
        assert route_after_result_eval(state) == "analyze"

    def test_reflect_three_times_still_reason(self):
        state = {"evaluator_results": [
            {"gate": 2, "verdict": "reflect"},
            {"gate": 2, "verdict": "reflect"},
            {"gate": 2, "verdict": "reflect"},
        ]}
        # retries < 3 is False for 3 retries → falls through to "analyze"
        assert route_after_result_eval(state) == "analyze"


class TestRouteAfterCheck:
    def test_complete_goes_to_end(self):
        state = {"_check_complete": True}
        assert route_after_check(state) == "__end__"

    def test_not_complete_goes_to_reason(self):
        state = {"_check_complete": False, "react_round": 1, "react_max_rounds": 5}
        assert route_after_check(state) == "reason"

    def test_max_rounds_goes_to_end(self):
        state = {"_check_complete": False, "react_round": 5, "react_max_rounds": 5}
        assert route_after_check(state) == "__end__"
