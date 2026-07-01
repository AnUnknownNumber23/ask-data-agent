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


def _tokenize(text: str) -> list[str]:
    """Split text into search tokens: words, CJK bigrams, and underscore parts.

    'order_date' -> ['order_date', 'order', 'date']
    'product_category_name' -> ['product_category_name', 'product', 'category', 'name']
    """
    tokens = list(text.lower().split())  # space-separated words
    # Split underscore/camelCase identifiers into sub-tokens
    for token in list(tokens):
        parts = re.split(r'[_]', token)  # order_date -> [order, date]
        for p in parts:
            if p and p not in tokens:
                tokens.append(p)
    _add_cjk_tokens(text, tokens)
    return [t for t in tokens if t]  # remove empty strings


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

        # Add date range constraint — prevent LLM from querying non-existent dates
        try:
            date_result = await self.dw.execute(
                "SELECT MIN(order_purchase_timestamp), MAX(order_purchase_timestamp) FROM orders"
            )
            if date_result.rows and date_result.rows[0][0]:
                min_d, max_d = date_result.rows[0][0], date_result.rows[0][1]
                range_doc = (
                    f"DATA DATE RANGE: {min_d} to {max_d}. "
                    f"The database ONLY contains data from {min_d} to {max_d}. "
                    f"DO NOT query dates outside this range. DO NOT use CURRENT_DATE, NOW(), or future dates. "
                    f"For 'last month', '上个月', or 'this year', the user likely means relative to the data's end ({max_d}), not today. "
                    f"If the relative time is ambiguous (e.g. 'last month' when data ends years ago), ASK the user to clarify which period they mean."
                )
                self.collection.upsert(
                    ids=["meta:date_range"],
                    documents=[range_doc],
                    metadatas=[{"type": "meta", "name": "date_range"}],
                )
                count += 1
        except Exception:
            pass  # date range is optional, not all DWs have orders table

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
        """Fallback keyword search (supports Chinese + underscore splitting)."""
        tokens = _tokenize(query)
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
        """Fallback keyword search for columns (supports Chinese + underscore splitting)."""
        tokens = _tokenize(query)
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

    def _merge(self, a: list[dict], b: list[dict], n: int,
               vec_weight: float = 0.6, kw_weight: float = 0.4) -> list[dict]:
        """Merge vector and keyword results with weighted scores.

        Keyword results have artificially low distances (0.05 = perfect match)
        which would always beat semantic results (0.2-0.8). We normalize keyword
        distances to be comparable with vector distances before merging.
        """
        seen = set()
        merged = []

        # Vector results: keep original distance (cosine distance, 0-2 range)
        for r in a:
            rid = r.get("id", "")
            if rid not in seen:
                seen.add(rid)
                r["_score"] = vec_weight * (1.0 - min(r.get("distance", 1.0), 1.0))
                r["_source"] = "vector"
                merged.append(r)

        # Keyword results: normalize distance to comparable range
        # Keyword distance is 1.0 - keyword_score. A perfect kw match = 0.05 distance
        # We map this to a comparable score: 1.0 - (kw_distance * 4)
        for r in b:
            rid = r.get("id", "")
            if rid not in seen:
                seen.add(rid)
                kw_dist = r.get("distance", 0.5)
                # Normalize: distance 0.05 -> score 0.8, distance 0.5 -> score -1.0
                normalized = 1.0 - min(kw_dist * 4, 1.0)
                r["_score"] = kw_weight * max(normalized, 0.0)
                r["_source"] = "keyword"
                merged.append(r)
            else:
                # Document already exists from vector search — boost its score
                for existing in merged:
                    if existing.get("id") == rid:
                        kw_dist = r.get("distance", 0.5)
                        normalized = 1.0 - min(kw_dist * 4, 1.0)
                        existing["_score"] = existing["_score"] + kw_weight * max(normalized, 0.0)
                        break

        merged.sort(key=lambda r: r.get("_score", 0), reverse=True)
        # Clean up internal fields
        for r in merged:
            r.pop("_score", None)
            r.pop("_source", None)
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
