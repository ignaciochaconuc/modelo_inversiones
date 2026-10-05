from pathlib import Path
import pandas as pd

class ParquetStore:
    """Small append-oriented Parquet store partitioned by optional columns."""
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, frame: pd.DataFrame, name: str, partition_cols: list[str] | None = None) -> Path:
        destination = self.root / name
        if partition_cols:
            destination.mkdir(parents=True, exist_ok=True)
            frame.to_parquet(destination, index=False, partition_cols=partition_cols)
        else:
            if destination.suffix != ".parquet":
                destination = destination.with_suffix(".parquet")
            frame.to_parquet(destination, index=False)
        return destination

    def read(self, name: str, filters: list[tuple[str, str, object]] | None = None) -> pd.DataFrame:
        path = self.root / name
        if not path.exists() and path.suffix != ".parquet":
            path = path.with_suffix(".parquet")
        return pd.read_parquet(path, filters=filters)
