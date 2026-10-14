"""Prepare or explicitly authorize a 32-case synthetic evaluation; never score."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path

_spec = importlib.util.spec_from_file_location("nacho_attribution_runner",
    Path(__file__).resolve().parents[1] / "tools/evaluation/nacho_attribution_runner.py")
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)
OUTPUT_ROOT = runner.OUTPUT_ROOT
preflight, validate_authorization = runner.preflight, runner.validate_authorization
execute_cases, review_module, sha = runner.execute_cases, runner.review_module, runner.sha
from investment_system.core.environment import load_repository_environment, safe_cli_errors


@safe_cli_errors
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--budget-usd", type=float, default=1.60)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--confirm-real-inference", action="store_true")
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if args.validate_only == args.confirm_real_inference:
        print(json.dumps({"status": "blocked", "error": "exactly_one_execution_mode_required", "provider_calls": 0}))
        return 2
    repo = Path(__file__).resolve().parents[1]
    plan, settings, requests = preflight(repo, args.config, args.budget_usd)
    if args.validate_only:
        print(json.dumps({"status": "validated_offline", "provider_calls": 0, "persistence_writes": 0, "plan": plan}))
        return 0
    if not args.authorization or not args.run_id:
        print(json.dumps({"status": "blocked", "error": "explicit_authorization_record_required", "provider_calls": 0}))
        return 2
    auth = json.loads(args.authorization.read_bytes())
    validate_authorization(auth, plan, args.run_id, datetime.now(timezone.utc))
    root = repo / OUTPUT_ROOT / args.run_id
    if root.exists():
        raise ValueError("run_identity_already_used_no_automatic_resume")
    # Only after validation of explicit owner authorization, not just a key/flag.
    load_repository_environment(real_operation_authorized=True)
    if not os.getenv("OPENAI_API_KEY"):
        print(json.dumps({"status": "blocked", "error": "missing_api_key", "provider_calls": 0}))
        return 2
    # Never persist credentials, even when accidentally included in authorization.
    secret = os.environ["OPENAI_API_KEY"]
    if any(secret in text for text in [json.dumps(auth), settings.model_dump_json(), json.dumps(plan)]):
        raise ValueError("secret_in_evaluation_metadata")
    from investment_system.llm.openai_client import OpenAIClient
    from investment_system.llm.router import LLMRouter
    from investment_system.agents.news_interpretation.persistence import LocalInterpretationStore
    from investment_system.agents.news_interpretation.service import NewsInterpretationService
    # Atomic new directory claims the run identity. Never overwrite/resume.
    root.mkdir(parents=True, exist_ok=False)
    review = review_module()
    review.write_json(root / "plan.json", plan)
    review.write_json(root / "authorization.json", auth)
    client = OpenAIClient(settings.adapter, enabled=True)
    router = LLMRouter({"openai": client}, {"news_interpretation": {"provider": "openai", "model": settings.adapter.model}})
    storage = LocalInterpretationStore(root / "runtime", allowed_root=repo / OUTPUT_ROOT)
    service = NewsInterpretationService(router, settings, storage, args.run_id, execution_authorized=True)
    def before_call():
        validate_authorization(auth, plan, args.run_id, datetime.now(timezone.utc))
        if sha(repo / runner.FREEZE_PATH) != runner.FREEZE_SHA256 or sha(args.config) != plan["config_sha256"]:
            raise ValueError("evaluation_artifact_changed_during_run")

    export = execute_cases(requests, service, root, plan, before_call=before_call)
    print(json.dumps({"status": "system_outputs_exported", "cases": len(export["cases"]),
                      "provider_attempts": len(service.tracker.records), "accounted_usd": export["accounted_usd"],
                      "unknown_cost_attempts": export["unknown_cost_attempts"],
                      "export_sha256": sha(root / "nacho-outputs.json"), "operational": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
