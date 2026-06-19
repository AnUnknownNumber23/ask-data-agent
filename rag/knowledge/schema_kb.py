"""Schema Knowledge Base — syncs DW metadata to ChromaDB for semantic search."""
import re
import chromadb
from connectors.dw.base import BaseDWConnector, TableSchema, ColumnInfo
from rag.embedding import get_embedding_function


def _add_cjk_tokens(text: str, tokens: list[str]) -> None:
    """Add CJK bigram tokens for queries without spaces between words."""
    cjk = re.findall(r'[一-鿿㐀-䶿豈-﫿]+', text)
    for segment in cjk:
        for i in range(len(segment) - 1):
            tokens.append(segment[i:i+2])
        for ch in segment:
            tokens.append(ch)


class SchemaKB:
    def __init__(self, dw: BaseDWConnector, chroma_path: str):
        self.dw = dw
        self.client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.client.get_or_create_collection(
            name="schema_kb",
            metadata={"description": "Table schemas from data warehouse"},
            embedding_function=get_embedding_function(),
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
        formatted = self._format_results(results)
        # Merge with keyword results (vector unreliable with hash embeddings)
        kw = self.keyword_search_tables(query, n=n)
        return self._merge(formatted, kw, n)

    def search_columns(self, query: str, table: str | None = None, n: int = 10) -> list[dict]:
        conditions = [{"type": "column"}]
        if table:
            conditions.append({"table": table})
        where = {"$and": conditions} if len(conditions) > 1 else conditions[0]
        results = self.collection.query(query_texts=[query], n_results=n, where=where)
        formatted = self._format_results(results)
        # Merge with keyword results
        kw = self.keyword_search_columns(query, table=table, n=n)
        return self._merge(formatted, kw, n)

    def exact_column_lookup(self, column_name: str) -> list[dict]:
        results = self.collection.get(where={"$and": [{"type": "column"}, {"name": column_name}]})
        if not results["ids"]:
            return []
        return [{"id": rid, "document": doc, "metadata": meta}
                for rid, doc, meta in zip(results["ids"], results["documents"] or [], results["metadatas"] or [])]

    def keyword_search_tables(self, query: str, n: int = 5) -> list[dict]:
        """Fallback keyword search (supports Chinese via bigram tokenization)."""
        query_lower = query.lower()
        tokens = list(query_lower.split())
        _add_cjk_tokens(query, tokens)
        results = []
        all_tables = self.collection.get(where={"type": "table"})
        if not all_tables["ids"]:
            return results
        for i, rid in enumerate(all_tables["ids"]):
            doc = (all_tables.get("documents") or [""])[i] if all_tables.get("documents") else ""
            meta = (all_tables.get("metadatas") or [{}])[i] if all_tables.get("metadatas") else {}
            doc_lower = doc.lower()
            name = meta.get("name", "").lower()
            score = 0.0
            for token in tokens:
                if token and token in name:
                    score += 0.5
                elif token and token in doc_lower:
                    score += 0.2
            if score > 0:
                results.append({"id": rid, "document": doc, "metadata": meta, "distance": 1.0 - min(score, 0.95)})
        results.sort(key=lambda r: r["distance"])
        return results[:n]

    def keyword_search_columns(self, query: str, table: str | None = None, n: int = 10) -> list[dict]:
        """Fallback keyword search for columns (supports Chinese via bigrams)."""
        query_lower = query.lower()
        tokens = list(query_lower.split())
        _add_cjk_tokens(query, tokens)
        results = []
        where = {"type": "column"}
        all_cols = self.collection.get(where=where)
        if not all_cols["ids"]:
            return results
        for i, rid in enumerate(all_cols["ids"]):
            doc = (all_cols.get("documents") or [""])[i] if all_cols.get("documents") else ""
            meta = (all_cols.get("metadatas") or [{}])[i] if all_cols.get("metadatas") else {}
            doc_lower = doc.lower()
            name = meta.get("name", "").lower()
            col_table = meta.get("table", "").lower()
            if table and col_table != table.lower():
                continue
            score = 0.0
            for token in tokens:
                if token and token in name:
                    score += 0.5
                elif token and token in doc_lower:
                    score += 0.2
            if score > 0:
                results.append({"id": rid, "document": doc, "metadata": meta, "distance": 1.0 - min(score, 0.95)})
        results.sort(key=lambda r: r["distance"])
        return results[:n]

    def _table_to_doc(self, schema: TableSchema) -> str:
        cols_desc = ", ".join(f"{c.name} ({c.dtype})" for c in schema.columns)
        return f"Table {schema.name}: {cols_desc}. {schema.row_count} rows."

    def _column_to_doc(self, table: str, col: ColumnInfo) -> str:
        nullable = "nullable" if col.nullable else "required"
        return f"Column {table}.{col.name}: type {col.dtype}, {nullable}. {col.comment}"

    def _merge(self, a: list[dict], b: list[dict], n: int) -> list[dict]:
        """Merge two result lists, deduplicate by id, sort by distance."""
        seen = set()
        merged = []
        for r in a + b:
            rid = r.get("id", "")
            if rid not in seen:
                seen.add(rid)
                merged.append(r)
        merged.sort(key=lambda r: r.get("distance", 1.0))
        return merged[:n]

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
