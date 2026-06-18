from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ColumnInfo:
    name: str
    dtype: str
    nullable: bool = True
    comment: str = ""


@dataclass
class TableSchema:
    name: str
    columns: list[ColumnInfo]
    row_count: int
    relations: list[dict[str, str]] = field(default_factory=list)


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple[Any, ...]]
    total_returned: int
    limit_applied: int | None = None
    execution_ms: float = 0.0

    @property
    def row_count(self) -> int:
        return len(self.rows)


class BaseDWConnector(ABC):
    """Pluggable data warehouse connector interface."""

    @abstractmethod
    async def execute(self, sql: str) -> QueryResult:
        """Execute a read-only SQL query."""
        ...

    @abstractmethod
    async def describe(self, table: str) -> TableSchema:
        """Get schema metadata for a table."""
        ...

    @abstractmethod
    async def list_tables(self) -> list[str]:
        """List all available tables."""
        ...

    @abstractmethod
    async def health(self) -> bool:
        """Check connectivity."""
        ...
