"""Conservative economic attribution v3; identity is never proof of participation."""
from datetime import datetime
import hashlib
import json
import re
from typing import Literal

from pydantic import Field, ValidationError, model_validator

from investment_system.data.news_entities import fingerprint
from investment_system.llm.schemas import LLMRequest, LLMResponse
from investment_system.agents.news_interpretation.schemas import (
    InterpretationModel, EvidenceSpan, ExtractedNewsEvent, InterpretationPayload,
    ModelConfiguration, NewsInterpretationRequest, RecordedLLMResponse,
)
from investment_system.agents.news_interpretation.replay import replay_response, validate_payload_evidence, _unique_json_object
from investment_system.agents.news_interpretation.grounding import (
    SelectedQuote, QuoteSelectionPayload, SelectedEvent, _selection_model, prepare_quote_request,
    GroundingResolution, GroundedInterpretationResult, RejectionDiagnostic, Stage, Rule,
    _SAFE_FIELDS, _RULES, resolve_quote_fields, QuoteResolutionError,
)

MODEL_OUTPUT_VERSION="news-economic-selection-v3"
PROMPT_VERSION="news-interpretation-prompt-v3"
VALIDATION_VERSION="news-economic-validation-v3"
ATTRIBUTION_VERSION="news-economic-attribution-v1"
Class=Literal["direct_participant","supported_indirect","contextual_mention","unknown"]
Role=Literal["buyer","target","investor","issuer","supplier","customer","contract_party","partner","regulator","legal_subject","unknown"]
Relation=Literal["transaction","supply_contract","partnership","regulation","litigation","ownership","competition","platform_license","unknown"]
RelationState=Literal["reported","uncertain","negated","unknown"]


class SelectedImpact(InterpretationModel):
    status: Literal["not_assessed","unknown","potential"]="not_assessed"
    channel: Literal["unknown","commercial","operational","legal","ownership","competitive"]="unknown"
    evidence: SelectedQuote | None=None
    rationale: str | None=None


class EconomicEntitySelection(InterpretationModel):
    name: str=Field(min_length=1)
    mention_kind: Literal["company","subsidiary","product","platform","other","unknown"]
    evidence: SelectedQuote
    registry_entity_id: str | None=None
    identity_evidence: SelectedQuote | None=None
    attribution: Class
    participation_role: Role="unknown"
    relation_type: Relation="unknown"
    related_entity: str | None=None
    relation_state: RelationState="unknown"
    relationship_evidence: SelectedQuote | None=None
    potential_impact: SelectedImpact=Field(default_factory=SelectedImpact)


_EconomicSelectedEvent=_selection_model("EconomicSelectedEvent",SelectedEvent,{
    "entities":tuple[EconomicEntitySelection,...],
})
_EconomicSelectedPayload=_selection_model("_EconomicSelectedPayload",QuoteSelectionPayload,{
    "events":tuple[_EconomicSelectedEvent,...],
})


class EconomicSelectionPayload(_EconomicSelectedPayload):
    schema_version: Literal["news-economic-selection-v3"]


class CorporateIdentity(InterpretationModel):
    state: Literal["resolved","unknown"]
    entity_id: str | None=None
    security_id: str | None=None
    ticker: str | None=None
    canonical_name: str | None=None
    evidence: EvidenceSpan | None=None

    @model_validator(mode="after")
    def known_or_unknown(self):
        values=(self.entity_id,self.security_id,self.ticker,self.canonical_name,self.evidence)
        if (self.state=="resolved" and any(v is None for v in values)) or (self.state=="unknown" and any(v is not None for v in values)):
            raise ValueError("identity fields must be fully sourced or unknown")
        return self


class PotentialImpact(SelectedImpact):
    evidence: EvidenceSpan | None=None
    confirmed_exposure: Literal[False]=False


class EconomicEntity(EconomicEntitySelection):
    evidence: EvidenceSpan
    # Raw-model identity proposals are NOT carried as flat tickers or entity IDs.
    registry_entity_id: Literal[None]=Field(default=None,exclude=True)
    identity_evidence: Literal[None]=Field(default=None,exclude=True)
    identity: CorporateIdentity
    relationship_evidence: EvidenceSpan | None=None
    potential_impact: PotentialImpact=Field(default_factory=PotentialImpact)


class EconomicEvent(ExtractedNewsEvent):
    entities: tuple[EconomicEntity,...]=()


class EconomicPayload(InterpretationPayload):
    schema_version: Literal["news-economic-interpretation-v3"]="news-economic-interpretation-v3"
    events: tuple[EconomicEvent,...]=()


NewRule=Literal["identity_not_supported","identity_ambiguous","product_identity_forbidden","attribution_evidence_required",
    "attribution_not_explicit","attribution_state_conflict","contextual_participation_forbidden",
    "impact_not_supported","invalid_consumer_projection"]
_FIELDS=_SAFE_FIELDS | set(EconomicEntitySelection.model_fields) | set(CorporateIdentity.model_fields) | set(PotentialImpact.model_fields) | {"identity"}


class AttributionDiagnostic(RejectionDiagnostic):
    stage: Stage | Literal["identity","economic_attribution","consumer_contract"]
    rule: Rule | NewRule

    @model_validator(mode="after")
    def safe_path(self):
        if any(isinstance(v,str) and v not in _FIELDS | {"unknown_field"} for v in self.field_path):
            raise ValueError("unsafe attribution diagnostic path")
        return self


class AttributionError(ValueError):
    def __init__(self,stage,rule,path):
        super().__init__(rule)
        self.diagnostic=AttributionDiagnostic(stage=stage,rule=rule,field_path=path)


def _fail(rule,path,stage="economic_attribution"):
    raise AttributionError(stage,rule,path)


def _name_pattern(name: str) -> str:
    return r"(?<!\w)"+re.escape(name)+r"(?!\w)"


def _has_name(text: str,name: str) -> bool:
    return bool(re.search(_name_pattern(name),text,re.IGNORECASE))


def _materialize(transformed: dict,request: NewsInterpretationRequest) -> dict:
    """Resolve proposed identity ONLY from the request's already eligible registry."""
    for i,event in enumerate(transformed["events"]):
        for j,entity in enumerate(event["entities"]):
            path=("events",i,"entities",j,"identity")
            ref=entity.pop("registry_entity_id"); evidence=entity.pop("identity_evidence")
            identity=dict(state="unknown")
            if ref is None:
                if evidence is not None:_fail("identity_not_supported",path,"identity")
            else:
                if entity["mention_kind"] not in {"company","subsidiary"}:
                    _fail("product_identity_forbidden",path,"identity")
                matches=[e for e in request.registry_entries if e.entity_id==ref]
                if len(matches)>1:_fail("identity_ambiguous",path,"identity")
                if not matches or evidence is None:_fail("identity_not_supported",path,"identity")
                entry=matches[0]
                aliases={entry.corporate_name.casefold(),*(a.casefold() for a in entry.aliases)}
                if entity["name"].casefold() not in aliases or not _has_name(evidence["quote"],entity["name"]):
                    _fail("identity_not_supported",path,"identity")
                identity=dict(state="resolved",entity_id=entry.entity_id,security_id=entry.security_id,
                    ticker=entry.ticker,canonical_name=entry.corporate_name,evidence=evidence)
            entity["identity"]=identity
    transformed["schema_version"]="news-economic-interpretation-v3"
    return transformed


def legacy_projection(payload: EconomicPayload) -> InterpretationPayload:
    """Validation-only adapter, never an exposed legacy list of affected tickers."""
    data=payload.model_dump(mode="json"); data["schema_version"]="news-interpretation-v1"
    for event in data["events"]:
        event["entities"]=[dict(name=e["name"],role="unknown",evidence=e["evidence"],
            entity_id=e["identity"]["entity_id"],ticker=e["identity"]["ticker"]) for e in event["entities"]]
    return InterpretationPayload.model_validate(data)


# Deliberately small, versioned English relation frames. Unsupported syntax must
# remain contextual/unknown; no bag-of-words entity+verb proximity matching.
_LEAD=r"(?:[®™])?(?:,\s+[^,;.!?]{1,160},)?\s+(?:today\s+)?(?:announced\s+(?:that\s+)?it\s+(?:has\s+)?|has\s+)?"


def _explicit_relation(entity: EconomicEntity,event: EconomicEvent) -> bool:
    text=entity.relationship_evidence.quote
    name=_name_pattern(entity.name)
    peer=_name_pattern(entity.related_entity) if entity.related_entity else None
    if entity.attribution=="direct_participant":
        role=entity.participation_role
        if role in {"buyer","target"} and (event.event_type!="ma" or entity.relation_type!="transaction" or peer is None):return False
        if role=="buyer":pattern=name+_LEAD+r"(?:acquired|acquires|agreed to acquire|will acquire)\s+"+peer
        elif role=="target":pattern=peer+_LEAD+r"(?:acquired|acquires|agreed to acquire|will acquire)\s+"+name
        elif role=="contract_party" and entity.relation_type=="supply_contract" and peer:
            pattern=name+_LEAD+r"signed (?:a |an )?(?:supply|purchase) (?:agreement|contract) with\s+"+peer
        elif role=="supplier" and entity.relation_type=="supply_contract" and peer:
            pattern=name+_LEAD+r"will supply\s+"+peer+r"\s+under a (?:supply )?(?:agreement|contract)\b"
        elif role=="customer" and entity.relation_type=="supply_contract" and peer:
            pattern=name+_LEAD+r"signed a purchase (?:agreement|contract) with\s+"+peer
        elif role=="partner" and entity.relation_type=="partnership" and peer:
            pattern=name+_LEAD+r"(?:signed a partnership with|partnered with)\s+"+peer
        elif role=="investor" and entity.relation_type=="transaction" and event.event_type in {"investment","financing"} and peer:
            pattern=name+_LEAD+r"(?:invested in|provided financing to)\s+"+peer
        elif role=="issuer" and entity.relation_type=="transaction" and event.event_type=="financing":
            pattern=name+_LEAD+r"(?:issued (?:bonds|debt)|raised financing)\b"
        elif role=="regulator" and entity.relation_type=="regulation" and event.event_type=="regulation" and peer:
            pattern=name+_LEAD+r"(?:fined|sanctioned)\s+"+peer
        elif role=="legal_subject" and entity.relation_type=="litigation" and event.event_type=="litigation" and peer:
            pattern=name+_LEAD+r"(?:sued|filed a lawsuit against)\s+"+peer
        else:return False
    else:
        if not peer:return False
        relation=entity.relation_type
        if relation=="ownership":pattern=name+r"\s+is (?:a |the )?(?:subsidiary|parent company) of\s+"+peer
        elif relation=="competition":pattern=name+r"\s+(?:competes with|is a competitor of)\s+"+peer
        elif relation=="supply_contract":pattern=name+r"\s+(?:supplies|is a supplier of)\s+"+peer
        elif relation=="platform_license":pattern=name+r"\s+licenses (?:its |a )?platform to\s+"+peer
        else:return False
    return bool(re.search(pattern,text,re.IGNORECASE))


def validate_attribution(payload: EconomicPayload,request: NewsInterpretationRequest) -> None:
    for i,event in enumerate(payload.events):
        direct_names={e.name.casefold() for e in event.entities if e.attribution=="direct_participant"}
        for j,entity in enumerate(event.entities):
            path=("events",i,"entities",j)
            if not _has_name(entity.evidence.quote,entity.name):_fail("entity_name_not_grounded",path+("evidence",))
            if entity.attribution in {"contextual_mention","unknown"}:
                if (entity.participation_role!="unknown" or entity.relation_type!="unknown" or entity.related_entity is not None
                        or entity.relation_state!="unknown" or entity.relationship_evidence is not None
                        or entity.potential_impact.status not in {"not_assessed","unknown"}):
                    _fail("contextual_participation_forbidden",path)
            else:
                if entity.mention_kind not in {"company","subsidiary"}:
                    _fail("attribution_not_explicit",path)
                if entity.relationship_evidence is None or entity.relation_state=="unknown":
                    _fail("attribution_evidence_required",path+("relationship_evidence",))
                q=entity.relationship_evidence.quote
                if not _has_name(q,entity.name) or (entity.related_entity and not _has_name(q,entity.related_entity)):
                    _fail("attribution_not_explicit",path+("relationship_evidence",))
                if entity.related_entity and entity.related_entity.casefold()==entity.name.casefold():
                    _fail("attribution_not_explicit",path)
                if entity.attribution=="supported_indirect" and entity.participation_role!="unknown":
                    _fail("contextual_participation_forbidden",path+("participation_role",))
                if entity.attribution=="supported_indirect" and (not entity.related_entity or entity.related_entity.casefold() not in direct_names):
                    _fail("attribution_not_explicit",path+("related_entity",))
                if entity.attribution=="direct_participant":
                    state=event.state_evidence; relation=entity.relationship_evidence
                    if state.evidence_id!=relation.evidence_id or max(state.start,relation.start)>=min(state.end,relation.end):
                        _fail("attribution_not_explicit",path+("relationship_evidence",))
                uncertain=bool(re.search(r"\b(may|might|rumou?r|unconfirmed|expects?|expected)\b",q,re.IGNORECASE))
                negated=bool(re.search(r"\b(not|never|no|denied|denies)\b",q,re.IGNORECASE))
                if (uncertain and entity.relation_state=="reported") or (negated and entity.relation_state!="negated"):
                    _fail("attribution_state_conflict",path+("relation_state",))
                if not _explicit_relation(entity,event):_fail("attribution_not_explicit",path+("relationship_evidence",))
            impact=entity.potential_impact
            if impact.status=="potential":
                if (entity.attribution not in {"direct_participant","supported_indirect"}
                        or entity.relation_state not in {"reported","uncertain"} or event.negated
                        or impact.evidence is None or not impact.rationale or impact.channel=="unknown"):
                    _fail("impact_not_supported",path+("potential_impact",))
                if not _has_name(impact.evidence.quote,entity.name):_fail("impact_not_supported",path+("potential_impact",))
                if entity.relationship_evidence.evidence_id!=impact.evidence.evidence_id or max(entity.relationship_evidence.start,impact.evidence.start)>=min(entity.relationship_evidence.end,impact.evidence.end):
                    _fail("impact_not_supported",path+("potential_impact",))
            elif impact.evidence is not None or impact.rationale is not None or impact.channel!="unknown":
                _fail("impact_not_supported",path+("potential_impact",))
            if impact.rationale and re.search(r"\b(BUY|SELL|HOLD)\b|(?i:price target|expected return|portfolio weight)|\d\s*%",impact.rationale):
                _fail("prohibited_output",path+("potential_impact",))


class ConsumerEntity(InterpretationModel):
    name: str
    attribution: Class
    reported_participant: bool
    economic_ticker: str | None=None
    potential_impact: Literal["not_assessed","unknown","potential"]
    confirmed_exposure: Literal[False]=False
    operational: Literal[False]=False

    @model_validator(mode="after")
    def no_context_exposure(self):
        if self.attribution!="direct_participant" and (self.reported_participant or self.economic_ticker is not None):
            raise ValueError("context/indirect/unknown is not reported direct participation")
        if self.economic_ticker is not None and not self.reported_participant:
            raise ValueError("security attribution requires reported participation")
        if self.attribution in {"contextual_mention","unknown"} and self.potential_impact=="potential":
            raise ValueError("context cannot imply potential impact")
        return self


class EconomicResult(GroundedInterpretationResult):
    schema_version: Literal["news-economic-result-v3"]="news-economic-result-v3"
    prompt_version: Literal["news-interpretation-prompt-v3"]=PROMPT_VERSION
    validation_version: Literal["news-economic-validation-v3"]=VALIDATION_VERSION
    attribution_version: Literal["news-economic-attribution-v1"]=ATTRIBUTION_VERSION
    payload: EconomicPayload | None=None
    diagnostics: tuple[AttributionDiagnostic,...]=()


class EconomicResolution(GroundingResolution):
    attribution_version: Literal["news-economic-attribution-v1"]=ATTRIBUTION_VERSION
    resolved_payload: EconomicPayload | None=None
    diagnostics: tuple[AttributionDiagnostic,...]=()


def prepare_economic_request(request: NewsInterpretationRequest,configuration: ModelConfiguration) -> LLMRequest:
    llm=prepare_quote_request(request,configuration)
    header,_,body=llm.prompt.partition("{"); envelope=json.loads("{"+body)
    instructions="""news-interpretation-prompt-v3
Classify each entity separately as direct_participant, supported_indirect,
contextual_mention or unknown. Corporate recognition never proves participation.
Never return tickers: propose an unambiguous eligible registry_entity_id only
with exact identity_evidence containing its corporate name/alias; otherwise null.
Products/platforms are not their manufacturer: keep product identities unresolved.
Direct participation needs a role-specific quote explicitly connecting the named
company to this event; words appearing elsewhere in the quote are insufficient.
Indirect ownership/supply/competition/license relations require both named parties
and an explicit relationship; no subsidiary-to-parent ticker inheritance.
Context/unknown must have unknown participation_role/relation_type/relation_state,
null relationship_evidence/related_entity, and no potential economic impact.
Impact is only a conditional potential assessment with evidence and rationale,
never proven causality, confirmed exposure, numerical returns or trading signals.
If evidence is only a product mention, do NOT assign its manufacturer as a party.
Conservative supported English frames: X acquired Y; X signed a supply contract
with Y; X partnered with Y; X invested in Y; X issued bonds; X fined Y; X sued Y;
X is a subsidiary of Y; X competes with Y; X supplies Y; X licenses its platform to Y.
Unsupported/ambiguous syntax remains unknown/contextual or triggers abstention.
"""
    # Keep v2's exact quote/date/registry/PIT instructions; its version line is
    # replaced, not its historical constant or stored wire.
    instructions += header.split("\n",1)[1]
    envelope.update(schema_version=MODEL_OUTPUT_VERSION,model_output_version=MODEL_OUTPUT_VERSION,
        prompt_version=PROMPT_VERSION,attribution_version=ATTRIBUTION_VERSION,
        output_schema=EconomicSelectionPayload.model_json_schema())
    llm.prompt=instructions+json.dumps(envelope,ensure_ascii=False,sort_keys=True)
    llm.response_schema=EconomicSelectionPayload.model_json_schema()
    return llm


def _diagnostics(error: ValidationError,stage) -> tuple[AttributionDiagnostic,...]:
    values=[]
    for item in error.errors(include_input=False,include_url=False):
        rule=_RULES.get(str((item.get("ctx") or {}).get("error")),("structural_contract_violation",()))[0]
        path=tuple(v if isinstance(v,int) or v in _FIELDS else "unknown_field" for v in item["loc"])
        values.append(AttributionDiagnostic(stage=stage,rule=rule,field_path=path))
    return tuple(values)


def evaluate_economic_response(request: NewsInterpretationRequest,response: LLMResponse,
                               configuration: ModelConfiguration,**options):
    request=NewsInterpretationRequest.model_validate(request.model_dump(mode="json"))
    selected_fp=None; resolved=None; projected=None; traces=(); diagnostics=()
    try:parsed=json.loads(response.content,object_pairs_hook=_unique_json_object)
    except (ValueError,TypeError,RecursionError):diagnostics=(AttributionDiagnostic(stage="json",field_path=(),rule="invalid_json"),)
    if not diagnostics:
        try:
            selected=EconomicSelectionPayload.model_validate(parsed)
            selected_fp=fingerprint(selected.model_dump(mode="json"))
        except ValidationError as error:diagnostics=_diagnostics(error,"model_schema")
    if not diagnostics:
        try:
            transformed,traces=resolve_quote_fields(selected.model_dump(mode="json"),request,diagnostic_type=AttributionDiagnostic)
            transformed=_materialize(transformed,request)
            resolved=EconomicPayload.model_validate(transformed)
            projected=legacy_projection(resolved)
            validate_payload_evidence(projected,request)
            validate_attribution(resolved,request)
        except QuoteResolutionError as error:diagnostics=(error.diagnostic,)
        except AttributionError as error:diagnostics=(error.diagnostic,)
        except ValidationError as error:diagnostics=_diagnostics(error,"internal_schema")
        except ValueError as error:
            rule,path=_RULES.get(str(error),("semantic_contract_violation",()))
            diagnostics=(AttributionDiagnostic(stage="semantic_validation",rule=rule,field_path=path),)
    derived=response.model_copy(update={"content":projected.model_dump_json() if projected is not None and not diagnostics else "{}"})
    checked=replay_response(request,derived,configuration,**options)
    tokens=options.get("tokens_reported"); latency=options.get("latency_reported")
    provenance=RecordedLLMResponse.model_validate({**response.model_dump(exclude={"raw"}),
        "tokens_reported":tokens if tokens is not None else {"input_tokens","cached_input_tokens","output_tokens"}.issubset(response.model_fields_set),
        "latency_reported":latency if latency is not None else "latency_ms" in response.model_fields_set})
    values=checked.model_dump(mode="json")
    values.update(schema_version="news-economic-result-v3",prompt_version=PROMPT_VERSION,
        validation_version=VALIDATION_VERSION,attribution_version=ATTRIBUTION_VERSION,
        payload=resolved.model_dump(mode="json") if checked.status in {"interpreted","abstained"} else None,
        provenance=provenance.model_dump(mode="json"),response_fingerprint=fingerprint(provenance.model_dump(mode="json")),
        invocation_fingerprint=fingerprint({"request":request.request_id,"llm_request":prepare_economic_request(request,configuration).model_dump(mode="json"),
            "configuration":configuration.model_dump(mode="json"),"attribution_version":ATTRIBUTION_VERSION}),
        diagnostics=[d.model_dump(mode="json") for d in diagnostics])
    result=EconomicResult.model_validate(values)
    resolution=EconomicResolution(original_content_sha256=hashlib.sha256(response.content.encode()).hexdigest(),
        resolved_at=result.validated_at,selection_fingerprint=selected_fp,resolved_payload=resolved,traces=traces,diagnostics=diagnostics)
    return resolution,result


class EconomicReplayEnvelope(InterpretationModel):
    schema_version: Literal["news-economic-replay-v3"]="news-economic-replay-v3"
    request: NewsInterpretationRequest
    resolution: EconomicResolution
    result: EconomicResult

    @model_validator(mode="after")
    def verify(self):
        original=self.result.provenance
        response=LLMResponse(**original.model_dump(exclude={"tokens_reported","latency_reported"}))
        resolution,result=evaluate_economic_response(self.request,response,self.result.model_configuration,
            validated_at=self.result.validated_at,execution_mode=self.result.execution_mode,
            estimated_cost_usd=self.result.estimated_cost_usd,tokens_reported=original.tokens_reported,latency_reported=original.latency_reported)
        if resolution!=self.resolution or result!=self.result:raise ValueError("economic replay identity/transformation mismatch")
        return self

    @property
    def envelope_id(self) -> str:return fingerprint(self.model_dump(mode="json"))

    def consumer_entities(self) -> tuple[ConsumerEntity,...]:
        """Contract-only safe projection; no features, exposures or trading route."""
        validated=type(self).model_validate(self.model_dump(mode="json"))
        result=validated.result
        if result.status not in {"interpreted","abstained"}:return ()
        views=[]
        for event in result.payload.events:
            for entity in event.entities:
                participant=(entity.attribution=="direct_participant" and entity.relation_state=="reported"
                    and event.state=="confirmed" and not event.negated)
                views.append(ConsumerEntity(name=entity.name,attribution=entity.attribution,reported_participant=participant,
                    economic_ticker=entity.identity.ticker if participant and entity.identity.state=="resolved" else None,
                    potential_impact=entity.potential_impact.status))
        return tuple(views)
