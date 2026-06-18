"""Schema Knowledge Base — syncs DW metadata to ChromaDB for semantic search."""
import chromadb
from connectors.dw.base import BaseDWConnector, TableSchema, ColumnInfo


class SchemaKB:
    def __init__(self, dw: BaseDWConnector, chroma_path: str):
        self.dw = dw
        self.client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.client.get_or_create_collection(
            name="schema_kb",
            metadata={"description": "Table schemas from data warehouse"},
        )

    async def sync(self) -> int:
        """Pull all table schemas from DW and index in ChromaDB. Returns count of indexed items."""
        tables = await self.dw.list_tables()
        count = 0
        for table_name in tables:
            schema = await self.dw.describe(table_name)
            table_doc = self._table_to_doc(schema)
            self.collection.upsert(
                ids=[f"table:{table_name}"],
                documents=[table_doc],
                metadatas=[{"type": "table", "name": table_name, "row_count": schema.row_count}],
            )
            count += 1
            for col in schema.columns:
                col_doc = self._column_to_doc(table_name, col)
                self.collection.upsert(
                    ids=[f"col:{table_name}.{col.name}"],
                    documents=[col_doc],
                    metadatas=[{"type": "column", "table": table_name, "name": col.name, "dtype": col.dtype}],
                )
                count += 1
        return count

    def search_tables(self, query: str, n: int = 5) -> list[dict]:
        results = self.collection.query(query_texts=[query], n_results=n, where={"type": "table"})
        return self._format_results(results)

    def search_columns(self, query: str, table: str | None = None, n: int = 10) -> list[dict]:
        where = {"type": "column"}
        if table:
            where["table"] = table
        results = self.collection.query(query_texts=[query], n_results=n, where=where)
        return self._format_results(results)

    def exact_column_lookup(self, column_name: str) -> list[dict]:
        results = self.collection.get(where={"$and": [{"type": "column"}, {"name": column_name}]})
        if not results["ids"]:
            return []
        return [{"id": rid, "document": doc, "metadata": meta}
                for rid, doc, meta in zip(results["ids"], results["documents"] or [], results["metadatas"] or [])]

    def _table_to_doc(self, schema: TableSchema) -> str:
        cols_desc = ", ".join(f"{c.name} ({c.dtype})" for c in schema.columns)
        return f"Table {schema.name}: {cols_desc}. {schema.row_count} rows."

    def _column_to_doc(self, table: str, col: ColumnInfo) -> str:
        nullable = "nullable" if col.nullable else "required"
        return f"Column {table}.{col.name}: type {col.dtype}, {nullable}. {col.comment}"

    def _format_results(self, results: dict) -> list[dict]:
        formatted = []
        if not results.get("ids") or not results["ids"][0]:
            return formatted
        for i, rid in enumerate(results["ids"][0]):
            formatted.append({
                "id": rid,
                "document": results["documents"][0][i] if results.get("documents") else "",
                "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                "distance": results["distances"][0][i] if results.get("distances") else None,
            })
        return formatted
