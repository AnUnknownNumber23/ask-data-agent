"""Download Olist dataset from Kaggle and load into DuckDB."""
import os
import sys
import duckdb


def download_olist() -> str:
    """Download Olist dataset using kagglehub, return base directory."""
    import kagglehub
    path = kagglehub.dataset_download("olistbr/brazilian-ecommerce")
    print(f"Downloaded to: {path}")
    return path


def load_to_duckdb(csv_dir: str, db_path: str) -> None:
    """Load all 9 CSV files into DuckDB with proper types."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    con = duckdb.connect(db_path)

    tables = {
        "customers": "olist_customers_dataset.csv",
        "geolocation": "olist_geolocation_dataset.csv",
        "order_items": "olist_order_items_dataset.csv",
        "order_payments": "olist_order_payments_dataset.csv",
        "order_reviews": "olist_order_reviews_dataset.csv",
        "orders": "olist_orders_dataset.csv",
        "products": "olist_products_dataset.csv",
        "sellers": "olist_sellers_dataset.csv",
        "category_translation": "product_category_name_translation.csv",
    }

    for table_name, filename in tables.items():
        filepath = os.path.join(csv_dir, filename)
        con.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} AS
            SELECT * FROM read_csv_auto('{filepath}')
        """)
        count = con.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
        print(f"  {table_name}: {count} rows")

    con.close()
    print(f"Done. Database at: {db_path}")


def main():
    db_path = os.path.join(os.path.dirname(__file__), "..", "data", "olist.duckdb")
    db_path = os.path.abspath(db_path)

    csv_dir = download_olist()
    load_to_duckdb(csv_dir, db_path)


if __name__ == "__main__":
    main()
