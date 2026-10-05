from pathlib import Path
import subprocess
import sys

def test_feature_build_script_dry_run() -> None:
    root = Path(__file__).parents[2]
    result = subprocess.run(
        [sys.executable, "scripts/build_quantitative_feature_store.py", "--ticker", "AAPL", "--start", "2025-01-01", "--end", "2025-01-31", "--dry-run"],
        cwd=root, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert '"dry_run": true' in result.stdout
