import pytest
from evaluator.rules import SQLEvaluator, Verdict


class TestSQLEvaluator:
    @pytest.fixture
    def evaluator(self):
        return SQLEvaluator(max_limit=10000)

    # --- REJECT cases ---
    def test_reject_drop_table(self, evaluator):
        result = evaluator.check("DROP TABLE orders")
        assert result.verdict == Verdict.REJECT
        assert any("DROP" in e for e in result.errors)

    def test_reject_delete(self, evaluator):
        result = evaluator.check("DELETE FROM orders WHERE id=1")
        assert result.verdict == Verdict.REJECT
        assert result.checks["no_dangerous_op"] is False

    def test_reject_insert(self, evaluator):
        result = evaluator.check("INSERT INTO orders VALUES (1)")
        assert result.verdict == Verdict.REJECT

    def test_reject_update(self, evaluator):
        result = evaluator.check("UPDATE orders SET status='done'")
        assert result.verdict == Verdict.REJECT

    def test_reject_truncate(self, evaluator):
        result = evaluator.check("TRUNCATE TABLE orders")
        assert result.verdict == Verdict.REJECT

    def test_reject_limit_too_high(self, evaluator):
        result = evaluator.check("SELECT * FROM orders LIMIT 50000")
        assert result.verdict == Verdict.REJECT

    # --- WARN cases ---
    def test_warn_no_limit(self, evaluator):
        result = evaluator.check("SELECT * FROM orders")
        assert result.verdict == Verdict.WARN
        assert result.checks["has_limit"] is False

    def test_warn_sql_injection_pattern(self, evaluator):
        result = evaluator.check("SELECT * FROM orders WHERE id = '1' OR '1'='1'")
        assert result.verdict == Verdict.WARN
        assert any("injection" in w.lower() for w in result.warnings)

    # --- PASS cases ---
    def test_accept_valid_select(self, evaluator):
        sql = """SELECT customer_state, COUNT(*) as cnt
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.order_purchase_timestamp >= '2018-03-01'
GROUP BY customer_state
LIMIT 100"""
        result = evaluator.check(sql)
        assert result.verdict == Verdict.PASS
        assert result.checks["is_select"] is True
        assert result.checks["has_limit"] is True
        assert result.checks["no_dangerous_op"] is True

    def test_accept_select_with_subquery(self, evaluator):
        sql = """SELECT * FROM (
    SELECT state, count(*) as cnt FROM customers GROUP BY state
) sub LIMIT 10"""
        result = evaluator.check(sql)
        assert result.verdict == Verdict.PASS
