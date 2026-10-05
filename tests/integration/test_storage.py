import pandas as pd
from investment_system.data.storage.duckdb_store import DuckDBStore
from investment_system.data.storage.parquet_store import ParquetStore

def test_parquet_duckdb_roundtrip(tmp_path) -> None:
    path = ParquetStore(tmp_path).write(pd.DataFrame({"ticker": ["AAPL"], "value": [1.0]}), "features")
    with DuckDBStore() as store:
        result = store.query_parquet(path)
    assert result.to_dict("records") == [{"ticker": "AAPL", "value": 1.0}]
