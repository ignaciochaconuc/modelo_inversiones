"""Opt-in ONE-article real interpretation; never run during normal validation."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
from uuid import uuid4

import yaml

from investment_system.agents.news_interpretation.inputs import build_interpretation_request
from investment_system.agents.news_interpretation.runtime_schemas import InterpretationRuntimeSettings
from investment_system.agents.news_interpretation.persistence import LocalInterpretationStore
from investment_system.agents.news_interpretation.service import NewsInterpretationService
from investment_system.data.news_entities import load_entity_registry
from investment_system.data.storage.news_store import NewsStore
from investment_system.llm.openai_client import OpenAIClient
from investment_system.llm.router import LLMRouter


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-real-inference",action="store_true")
    parser.add_argument("--config",type=Path,required=True)
    parser.add_argument("--model",required=True)
    parser.add_argument("--budget-usd",type=float,required=True)
    parser.add_argument("--revision-id",required=True)
    parser.add_argument("--as-of",required=True)
    args=parser.parse_args()
    if not args.confirm_real_inference:
        print(json.dumps({"status":"disabled","error":"explicit_confirmation_required","provider_calls":0}))
        return 2
    # Environment ONLY; do not load dotenv or config-based credentials.
    if not os.getenv("OPENAI_API_KEY"):
        print(json.dumps({"status":"blocked","error":"missing_api_key","provider_calls":0}))
        return 2
    try:
        raw=yaml.safe_load(args.config.read_text(encoding="utf-8"))
        if os.getenv("OPENAI_API_KEY") in json.dumps(raw,default=str):
            raise ValueError("secrets are not configuration")
        if raw["adapter"]["model"] != args.model:
            raise ValueError("model flag must match the explicit profile")
        settings=InterpretationRuntimeSettings.model_validate(raw)
        if args.budget_usd <= 0 or args.budget_usd > settings.run_budget_usd:
            raise ValueError("flag cannot expand the configured budget")
        settings=InterpretationRuntimeSettings.model_validate({**settings.model_dump(mode="json"),
            "run_budget_usd":args.budget_usd,"request_budget_usd":min(settings.request_budget_usd,args.budget_usd)})
        cutoff=datetime.fromisoformat(args.as_of.replace("Z","+00:00"))
        request=build_interpretation_request(NewsStore("data/raw","data/processed"),args.revision_id,cutoff,registry=load_entity_registry())
        now=datetime.now().astimezone()
        if not settings.pricing.valid_from <= now < settings.pricing.valid_until:
            raise ValueError("pricing validity required")
    except (ValueError,TypeError,KeyError,OSError,yaml.YAMLError):
        print(json.dumps({"status":"blocked","error":"invalid_or_missing_critical_configuration","provider_calls":0}))
        return 2
    client=OpenAIClient(settings.adapter,enabled=True)
    router=LLMRouter({"openai":client},{"news_interpretation":{"provider":"openai","model":args.model}})
    service=NewsInterpretationService(router,settings,LocalInterpretationStore(),uuid4().hex,execution_authorized=True)
    try:
        delivery=service.interpret(request)
    except Exception:
        # Never expose exception strings/payloads; durable reservations remain.
        print(json.dumps({"status":"failed","error":"safe_execution_failure","experimental":True}))
        return 1
    record=delivery.record
    print(json.dumps({"status":record.outcome if record else "blocked","error":delivery.error_code,
        "retrieval_mode":delivery.retrieval_mode,"attempts":delivery.additional_attempts,
        "cost_usd":delivery.additional_provider_cost_usd,"conservative_accounted_usd":service.budget.accounted(),
        "unknown_cost_attempts":service.tracker.unknown_cost_count(),
        "tokens": [{"input":r.input_tokens,"cached":r.cached_input_tokens,"output":r.output_tokens} for r in service.tracker.records],
        "record_id":delivery.record_id,"cache_key":delivery.cache_key,
        "requested_model":args.model,"actual_model":record.actual_model if record else None,
        "experimental":True,"operational":False,"articles":1}))
    return 0 if record and record.outcome in {"interpreted","abstained"} else 1


if __name__=="__main__":
    raise SystemExit(main())
