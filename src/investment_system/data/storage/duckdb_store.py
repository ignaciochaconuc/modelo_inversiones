from pathlib import Path
from typing import Any
import duckdb
import pandas as pd

class DuckDBStore:
    def __init__(self, database: str | Path = ":memory:") -> None:
        self.connection = duckdb.connect(str(database))

    def query(self, sql: str, parameters: list[Any] | None = None) -> pd.DataFrame:
        return self.connection.execute(sql, parameters or []).fetchdf()

    def query_parquet(self, path: str | Path, where: str = "TRUE") -> pd.DataFrame:
        # Path is bound as a parameter; callers should only construct `where` from trusted code.
        return self.query(f"SELECT * FROM read_parquet(?) WHERE {where}", [str(path)])

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "DuckDBStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
