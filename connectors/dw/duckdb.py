import time
import duckdb
from pathlib import Path
from .base import BaseDWConnector, ColumnInfo, QueryResult, TableSchema


class DuckDBConnector(BaseDWConnector):
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self._con: duckdb.DuckDBPyConnection | None = None

    @property
    def con(self) -> duckdb.DuckDBPyConnection:
        if self._con is None:
            self._con = duckdb.connect(str(self.db_path), read_only=True)
        return self._con

    async def execute(self, sql: str) -> QueryResult:
        start = time.perf_counter()
        try:
            result = self.con.execute(sql)
            columns = [desc[0] for desc in result.description]
            rows = result.fetchall()
            elapsed = (time.perf_counter() - start) * 1000
            return QueryResult(
                columns=columns,
                rows=rows,
                total_returned=len(rows),
                execution_ms=elapsed,
            )
        except Exception as e:
            raise RuntimeError(f"Query failed: {e}") from e

    async def describe(self, table: str) -> TableSchema:
        cols = self.con.execute(f"DESCRIBE {table}").fetchall()
        columns = [
            ColumnInfo(name=c[0], dtype=c[1], nullable=c[3] == "YES")
            for c in cols
        ]
        count = self.con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        return TableSchema(name=table, columns=columns, row_count=count)

    async def list_tables(self) -> list[str]:
        rows = self.con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        return [r[0] for r in rows]

    async def health(self) -> bool:
        try:
            self.con.execute("SELECT 1")
            return True
        except Exception:
            return False
