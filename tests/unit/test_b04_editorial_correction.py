"""Byte-level editorial artifact tests, not evaluator-generated reference labels."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[2] / "tools/evaluation/prepare_b04_editorial_correction.py"
SPEC = importlib.util.spec_from_file_location("b04_editorial", PATH)
editor = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(editor)


def fixture(newline="\r\n", extra=None):
    value = {"cases":[{"case_id":editor.CASE_ID,"unchanged_label":"fixture-only",
        "units":[{"unit_id":editor.UNIT_ID,"role":"unchanged-fixture-role","dimensions":{
            "corporate_identity":{"evidence":[{"evidence_id":editor.CASE_ID+":summary","quote":editor.OLD_QUOTE}]}}}]}]}
    if extra:value["extra"] = extra
    raw = json.dumps(value,indent=2).replace("\n",newline).encode()
    packet = {"cases":[{"case_id":editor.CASE_ID,"evidence":[{
        "evidence_id":editor.CASE_ID+":summary","text":editor.NEW_QUOTE+", fixture continuation."}]}]}
    return raw,value,packet


def parse(text):
    return json.loads(text),"plain_json"


@pytest.mark.parametrize("newline", ["\r\n", "\n"])
def test_changes_one_byte_only_with_all_annotations_unchanged(monkeypatch,newline):
    raw,original,packet = fixture(newline)
    monkeypatch.setattr(editor,"ORIGINAL_SHA256",hashlib.sha256(raw).hexdigest())
    expected = deepcopy(original)
    expected["cases"][0]["units"][0]["dimensions"]["corporate_identity"]["evidence"][0]["quote"] = editor.NEW_QUOTE
    calls=[]
    def validate(value,p):
        assert value==expected and p==packet
        calls.append(value)
    corrected,trace = editor.build_candidate(raw,parse,validate,packet)
    assert len(calls)==1 and json.loads(corrected)==expected
    assert len(raw)==len(corrected) and sum(a!=b for a,b in zip(raw,corrected))==1
    assert raw.count(b"\r\n")==corrected.count(b"\r\n")
    assert trace["new_chatgpt_generation"] is False and trace["current_importer_used"] is False
    assert trace["all_other_bytes_unchanged"] and trace["all_other_annotation_values_unchanged"]


def test_hash_drift_rejected_without_editing():
    raw,_,packet = fixture()
    with pytest.raises(ValueError,match="hash_differs"):
        editor.build_candidate(raw,parse,lambda *a:None,packet)


def test_ambiguous_literal_location_rejected(monkeypatch):
    raw,_,packet = fixture(extra=editor.OLD_QUOTE)
    monkeypatch.setattr(editor,"ORIGINAL_SHA256",hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError,match="not_unique"):
        editor.build_candidate(raw,parse,lambda *a:None,packet)


def test_wrong_source_rejected(monkeypatch):
    raw,_,packet = fixture()
    monkeypatch.setattr(editor,"ORIGINAL_SHA256",hashlib.sha256(raw).hexdigest())
    packet["cases"][0]["evidence"][0]["text"] = "different fixture source"
    with pytest.raises(ValueError,match="not_in_original_source"):
        editor.build_candidate(raw,parse,lambda *a:None,packet)


def test_original_validator_failure_propagates(monkeypatch):
    raw,_,packet = fixture()
    monkeypatch.setattr(editor,"ORIGINAL_SHA256",hashlib.sha256(raw).hexdigest())
    def reject(*args):raise ValueError("fixture_original_validation_rule")
    with pytest.raises(ValueError,match="original_validation_rule"):
        editor.build_candidate(raw,parse,reject,packet)
