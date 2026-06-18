import pytest
from connectors.dw.duckdb import DuckDBConnector


@pytest.fixture
async def dw():
    conn = DuckDBConnector("data/olist.duckdb")
    yield conn


@pytest.mark.integration
class TestDuckDBConnector:
    async def test_list_tables(self, dw):
        tables = await dw.list_tables()
        assert "orders" in tables
        assert "customers" in tables
        assert "products" in tables
        assert len(tables) >= 9

    async def test_describe_orders(self, dw):
        schema = await dw.describe("orders")
        assert schema.name == "orders"
        col_names = [c.name for c in schema.columns]
        assert "order_id" in col_names
        assert "order_purchase_timestamp" in col_names
        assert "order_status" in col_names
        assert schema.row_count > 0

    async def test_execute_simple_query(self, dw):
        result = await dw.execute(
            "SELECT order_status, count(*) as cnt FROM orders GROUP BY order_status LIMIT 10"
        )
        assert len(result.columns) == 2
        assert result.total_returned > 0
        assert result.execution_ms >= 0

    async def test_execute_with_join(self, dw):
        sql = """
            SELECT c.customer_state, count(*) as order_count
            FROM orders o
            JOIN customers c ON o.customer_id = c.customer_id
            GROUP BY c.customer_state
            ORDER BY order_count DESC
            LIMIT 5
        """
        result = await dw.execute(sql)
        assert result.total_returned > 0
        assert "customer_state" in result.columns
        assert "order_count" in result.columns

    async def test_health(self, dw):
        assert await dw.health() is True

    async def test_bad_sql_raises(self, dw):
        with pytest.raises(RuntimeError):
            await dw.execute("SELECT * FROM nonexistent_table")
