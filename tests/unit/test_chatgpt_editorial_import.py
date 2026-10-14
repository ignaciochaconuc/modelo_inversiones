"""Offline chain adversaries; no real human/evaluator references or API calls."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("editorial_manual_review", REPO / "tools/evaluation/prepare_chatgpt_review.py")
tool = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(tool)
chain = tool.editorial_chain_module()


def serialized(value):
    return (json.dumps(value, ensure_ascii=False, indent=2)+"\n").encode()


def fixture_chain(packet, packet_hash="fixture-packet"):
    # All references are nonconclusive instrument placeholders; not corpus labels.
    data = {"block_id":packet["block_id"],"limitations":["offline instrument fixture only"],"cases":[
        {"case_id":c["case_id"],"evidence_fingerprint":c["evidence_fingerprint"],"status":"nonconclusive",
         "events":[],"units":[],"uncertainties":["fixture not real adjudication"]} for c in packet["cases"]]}
    source = packet["cases"][0]["evidence"][0]
    after = source["text"]; before = after[0].swapcase()+after[1:]
    data["cases"][0]["units"] = [{"unit_id":"fixture-unit","event_id":None,"name":"instrument fixture",
        "dimensions":{d:{"status":"uncertain","value":None,"rationale":"fixture only","evidence":[]} for d in tool.DIMENSIONS}}]
    data["cases"][0]["units"][0]["dimensions"]["corporate_identity"]["evidence"] = [{"evidence_id":source["evidence_id"],"quote":before}]
    original = serialized(data); corrected = original.replace(before.encode(),after.encode())
    change = {"operation":"replace_initial_ascii_case_in_quote",
        "json_pointer":"/cases/0/units/0/dimensions/corporate_identity/evidence/0/quote",
        "case_id":data["cases"][0]["case_id"],"unit_id":"fixture-unit","evidence_id":source["evidence_id"],
        "before":before,"after":after,"byte_offset_zero_based":original.index(before.encode()),
        "byte_before_hex":before[0].encode().hex(),"byte_after_hex":after[0].encode().hex(),
        "performed_by":"offline fixture editor","reason":"fixture case correction",
        "transformed_at":"2026-10-13T18:02:00Z"}
    manifest = {"version":chain.MANIFEST_VERSION,"policy":chain.POLICY,"block_id":packet["block_id"],
        "packet_sha256":packet_hash,"original_sha256":chain.digest(original),"corrected_sha256":chain.digest(corrected),
        "changes":[change],"legacy_artifact_manifest":None}
    auth = {"version":chain.AUTHORIZATION_VERSION,"approved":True,
        "authorized_action":"import_editorially_corrected_annotation","authorized_by":"offline fixture owner",
        "recorded_by":"offline instrument test","recorded_at":"2026-10-13T18:03:00Z","owner_authorized_at":None,
        "authorization_basis":"simulation only, no real authority or evaluator execution",
        "block_id":packet["block_id"],"policy":chain.POLICY,"original_sha256":chain.digest(original),
        "corrected_sha256":chain.digest(corrected),"manifest_sha256":chain.digest(serialized(manifest)),
        "allowed_changes_fingerprint":tool.fp(manifest["changes"]),"legacy_manifest_sha256":None}
    return original,corrected,manifest,auth


def toy_packet():
    return {"block_id":"B04","identity_evidence":{"entries":[]},"cases":[
        {"case_id":f"toy-{i}","evidence_fingerprint":f"fixture-{i}","evidence":[
            {"evidence_id":f"toy-{i}:headline","text":f"A purely fictional instrument sentence {i}","field":"headline"}]}
        for i in range(4)]}


def check(values, packet=None):
    return chain.verify_chain(*values, packet or toy_packet(), tool.parse, tool.validate_annotations, tool.timestamp, tool.fp)


def test_chain_preserves_all_non_quote_values_and_records_original_rejection():
    values = fixture_chain(toy_packet()); annotation,diagnostic = check(values)
    original,_ = tool.parse(values[0].decode()); expected=deepcopy(original)
    expected["cases"][0]["units"][0]["dimensions"]["corporate_identity"]["evidence"][0]["quote"] = values[2]["changes"][0]["after"]
    assert annotation==expected and diagnostic=={"status":"rejected","code":"quote_not_in_declared_case_field"}
    assert sum(a!=b for a,b in zip(values[0],values[1]))==1


@pytest.mark.parametrize("attack", ["not_approved","wrong_scope","no_owner","empty_list","wrong_allowlist",
    "wrong_original_hash","wrong_corrected_hash","wrong_offset","wrong_pointer","wrong_case","wrong_responsible","bad_timestamp"])
def test_rejects_unauthorized_or_incorrect_manifest(attack):
    original,corrected,manifest,auth = fixture_chain(toy_packet())
    if attack=="not_approved":auth["approved"]=False
    elif attack=="wrong_scope":auth["authorized_action"]="another action"
    elif attack=="no_owner":auth["authorized_by"]=""
    elif attack=="empty_list":manifest["changes"]=[]
    elif attack=="wrong_allowlist":auth["allowed_changes_fingerprint"]="0"*64
    elif attack=="wrong_original_hash":manifest["original_sha256"]="0"*64
    elif attack=="wrong_corrected_hash":manifest["corrected_sha256"]="0"*64
    elif attack=="wrong_offset":manifest["changes"][0]["byte_offset_zero_based"]+=1
    elif attack=="wrong_pointer":manifest["changes"][0]["json_pointer"]="/cases/0/units/0/name"
    elif attack=="wrong_case":manifest["changes"][0]["case_id"]="not-source-case"
    elif attack=="wrong_responsible":manifest["changes"][0]["performed_by"]=""
    else:manifest["changes"][0]["transformed_at"]="2026-10-13T18:02:00"
    if attack not in {"wrong_allowlist","empty_list"}:auth["allowed_changes_fingerprint"]=tool.fp(manifest["changes"])
    with pytest.raises(ValueError):check((original,corrected,manifest,auth))


@pytest.mark.parametrize("field", ["name","event_id","semantic_value","status"])
def test_hidden_semantic_edit_rejected_even_with_recomputed_derived_hash(field):
    original,corrected,manifest,auth = fixture_chain(toy_packet())
    data,_=tool.parse(corrected.decode()); unit=data["cases"][0]["units"][0]
    if field=="semantic_value":unit["dimensions"]["participation"]["value"]="invented participant"
    elif field=="status":data["cases"][0]["status"]="annotated"
    else:unit[field]="hidden semantic change"
    corrected=serialized(data);manifest["corrected_sha256"]=auth["corrected_sha256"]=chain.digest(corrected)
    with pytest.raises(ValueError):check((original,corrected,manifest,auth))


def test_substantive_quote_rewrite_is_rejected_even_if_authorized():
    original,corrected,manifest,auth = fixture_chain(toy_packet())
    manifest["changes"][0]["after"]="A different claim"
    auth["allowed_changes_fingerprint"]=tool.fp(manifest["changes"])
    with pytest.raises(ValueError,match="non_editorial"):
        check((original,corrected,manifest,auth))


def test_legacy_manifest_hash_and_fields_must_match():
    original,corrected,manifest,auth = fixture_chain(toy_packet());c=manifest["changes"][0]
    legacy={k:c[k] for k in ("before","after","json_pointer","case_id","unit_id","evidence_id","byte_offset_zero_based",
        "byte_before_hex","byte_after_hex","performed_by","reason","transformed_at")}
    legacy.update(transformation_version="b04-editorial-artifact-v1",new_chatgpt_generation=False,bytes_changed=1,
        block_id="B04",original_sha256=chain.digest(original),corrected_sha256=chain.digest(corrected),
        packet_sha256=manifest["packet_sha256"],authorized_by=auth["authorized_by"])
    manifest["legacy_artifact_manifest"]=chain.text_artifact(serialized(legacy));auth["legacy_manifest_sha256"]=manifest["legacy_artifact_manifest"]["sha256"]
    check((original,corrected,manifest,auth))
    manifest["legacy_artifact_manifest"]["utf8"]+="tamper"
    with pytest.raises(ValueError,match="hash_mismatch"):check((original,corrected,manifest,auth))


def provenance(output,bid):
    prov=json.loads((output/f"templates/{bid}.provenance.json").read_bytes())
    prov.update(recorded_by="offline fixture recorder",model_label_visibility="not_exposed",started_at="2026-10-13T18:00:00Z",
        completed_at="2026-10-13T18:01:00Z",fresh_conversation_declared=True,system_outputs_seen=False,
        context_limitations=["offline test, no actual ChatGPT execution"])
    return prov


def mixed_imports(tmp_path):
    output=tmp_path/"prepared";tool.prepare(REPO,output);imports=tmp_path/"imports";legacy_bytes={}
    for i in range(1,9):
        bid=f"B{i:02d}";packet=tool.packet_for(REPO,output,bid);prov=tmp_path/f"{bid}.provenance.json";tool.write_json(prov,provenance(output,bid))
        if bid=="B04":
            original,corrected,manifest,auth=fixture_chain(packet,tool.sha(output/f"packets/{bid}.md"))
            paths=[tmp_path/"original.txt",tmp_path/"corrected.txt",tmp_path/"changes.json",tmp_path/"authorization.json"]
            for p,raw in zip(paths,[original,corrected,serialized(manifest),serialized(auth)]):p.write_bytes(raw)
            tool.import_editorial_response(REPO,output,bid,*paths,prov,imports/f"{bid}.json")
        else:
            data={"block_id":bid,"limitations":[],"cases":[{"case_id":c["case_id"],"evidence_fingerprint":c["evidence_fingerprint"],
                "status":"nonconclusive","events":[],"units":[],"uncertainties":["fixture"]} for c in packet["cases"]]}
            response=tmp_path/f"{bid}.txt";tool.write_json(response,data)
            tool.import_response(REPO,output,bid,response,prov,imports/f"{bid}.json")
            legacy_bytes[bid]=(imports/f"{bid}.json").read_bytes()
    return output,imports,legacy_bytes


def test_import_is_idempotent_and_mixed_freeze_reconstructs_all_chains(tmp_path):
    output,imports,legacy=mixed_imports(tmp_path)
    record=json.loads((imports/"B04.json").read_bytes())
    assert record["version"]==chain.VERSION and record["new_chatgpt_generation"] is False
    assert record["original_provider_response"]["utf8"]!=(record["editorially_corrected_annotation"]["utf8"])
    assert tool.verify_import_record(REPO,output,record,"B04")==record["annotations"]
    before=(imports/"B04.json").read_bytes()
    tool.import_editorial_response(REPO,output,"B04",tmp_path/"original.txt",tmp_path/"corrected.txt",
        tmp_path/"changes.json",tmp_path/"authorization.json",tmp_path/"B04.provenance.json",imports/"B04.json")
    assert (imports/"B04.json").read_bytes()==before
    result=tool.freeze(REPO,output,imports,tmp_path/"freeze.json")
    assert result["cases"]==32 and json.loads((tmp_path/"freeze.json").read_bytes())["version"]==chain.VERSION
    assert all((imports/f"{bid}.json").read_bytes()==raw for bid,raw in legacy.items())


@pytest.mark.parametrize("attack", ["original","derived","manifest","authorization","annotations","new_generation"])
def test_freeze_rejects_tampered_chain_even_with_rehashed_record(tmp_path,attack):
    output,imports,_=mixed_imports(tmp_path);path=imports/"B04.json";record=json.loads(path.read_bytes())
    keys={"original":"original_provider_response","derived":"editorially_corrected_annotation",
          "manifest":"editorial_correction_manifest","authorization":"correction_authorization"}
    if attack in keys:record[keys[attack]]["utf8"]+="tamper"
    elif attack=="annotations":record["annotations"]["cases"][0]["uncertainties"].append("hidden mutation")
    else:record["new_chatgpt_generation"]=True
    record["record_id"]=tool.fp({k:v for k,v in record.items() if k!="record_id"});path.write_bytes(serialized(record))
    with pytest.raises(ValueError):tool.freeze(REPO,output,imports,tmp_path/"bad-freeze.json")
    assert not (tmp_path/"bad-freeze.json").exists()
