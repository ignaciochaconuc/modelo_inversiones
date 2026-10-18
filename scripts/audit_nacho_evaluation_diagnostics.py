"""Audit a pinned evaluation manifest and sidecars without reading response content."""
import argparse
import importlib.util
import json
from pathlib import Path

from investment_system.core.environment import safe_cli_errors


@safe_cli_errors
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("nacho_diagnostic_audit",
        repo / "tools/evaluation/nacho_evaluation_diagnostics.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    print(json.dumps(module.audit(args.manifest, args.expected_sha256,
        store=module.SidecarStore(repo / module.ROOT, allowed_root=repo / module.ROOT))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
