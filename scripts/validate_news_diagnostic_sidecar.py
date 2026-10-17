"""Offline schema/retention preflight or metadata-only audit. No inference mode."""
import argparse
from datetime import datetime, timedelta, timezone
import json

from investment_system.agents.news_interpretation.diagnostic_events import BranchDiagnostic
from investment_system.agents.news_interpretation.diagnostic_sidecar import (
    DiagnosticSidecar, SidecarStore, VERSION, POLICY, RETENTION_DAYS,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--audit", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--case-id")
    parser.add_argument("--expected-id")
    args = parser.parse_args()
    try:
        if args.validate_only:
            now = datetime.now(timezone.utc)
            # Metadata specimen only: no text, interpretation request or provider.
            value = DiagnosticSidecar(run_id="eval-" + "0" * 32, case_id="S-" + "0" * 16,
                created_at=now, expires_at=now+timedelta(days=RETENTION_DAYS), attempt_started_at=now,
                outcome="rejected", native_outcome="invalid_response", error_code="invalid_structured_evidence",
                pipeline_stage="semantic_validation", rejection_code="stage_not_supported",
                request_id="0"*64, revision_id="0"*64, source_evidence_fingerprint="0"*64,
                request_evidence_fingerprint="0"*64, settings_fingerprint="0"*64, wire_fingerprint="0"*64,
                cache_key="0"*64, attempt_id="0"*32, record_id="0"*64, validation_observed=True,
                diagnostics=(BranchDiagnostic(stage="semantic_validation", rule="stage_not_supported",
                    subcode="completion_literal_missing", field_path=("events",0,"state_evidence")),))
            DiagnosticSidecar.model_validate_json(value.model_dump_json())
            print(json.dumps({"status":"validated_offline", "schema_version":VERSION,"retention_policy":POLICY,
                "retention_days":RETENTION_DAYS,"provider_calls":0,"credential_loads":0,"persistence_writes":0}))
        else:
            if not args.run_id or not args.case_id or not args.expected_id:
                raise ValueError("explicit_metadata_identity_required")
            value = SidecarStore().read(args.run_id, args.case_id, expected_id=args.expected_id)
            print(json.dumps({"sidecar_id":value.sidecar_id,"metadata":value.model_dump(mode="json")}))
        return 0
    except Exception:
        # No exception/body/extra-key echo even for malformed adversarial metadata.
        print(json.dumps({"status":"blocked","error":"diagnostic_preflight_or_audit_failed","provider_calls":0}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
