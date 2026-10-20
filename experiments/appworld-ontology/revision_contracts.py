"""OWB02 contracts. These add explicit evidence and obligations to the v1 graph."""
from typing import Any, Literal
from pydantic import Field
from contracts import Strict, KernelPlan, Citation, Fact, Edge, Selection, Extraction, check_extraction


class ContextPolicy(Strict):
    name: str
    extraction_rules: list[str] = Field(min_length=1)
    action_rules: list[str] = Field(min_length=1)
    initial_obligations: list[str] = Field(min_length=1)
    retain_partial_facts: Literal[True]
    require_property_sources: Literal[True]


class Change(Strict):
    target: str
    before: str
    after: str
    reason: str
    evidence_event_ids: list[str] = Field(min_length=1)


class RepairBundle(Strict):
    kernel: KernelPlan
    context_policy: ContextPolicy
    changes: list[Change] = Field(min_length=1)
    share_type: str
    status_property: str
    unpaid_value: str
    paid_value: str
    outstanding_function: Literal['onto_outstanding_shares']


class GroundedFact(Fact):
    property_sources: dict[str,list[Citation]]


class Obligation(Strict):
    description: str
    status: Literal['unresolved','satisfied']
    sources: list[Citation]


class RevisedExtraction(Strict):
    facts: list[GroundedFact]
    edges: list[Edge]
    selection: Selection
    gaps: list[str]
    obligations: list[Obligation]


class WithheldClaim(Strict):
    fact_id: str
    property: str
    reason: str


class GroundingReview(Strict):
    unsupported_claims: list[WithheldClaim]
    reopened_obligations: list[str]
    summary: str


def check_revised(extraction,candidate,sources):
    base=Extraction.model_validate(extraction.model_dump(exclude={'obligations','facts'}) | {
        'facts':[f.model_dump(exclude={'property_sources'}) for f in extraction.facts]})
    checks=check_extraction(base,candidate,sources,allow_partial=True)
    for fact in extraction.facts:
        if set(fact.property_sources)!=set(fact.properties):
            raise ValueError('Every asserted property needs its own source references')
        for citations in fact.property_sources.values():
            if not citations:
                raise ValueError('Empty property citations')
            for citation in citations:
                if citation.source_id not in sources or citation.quote not in sources[citation.source_id]:
                    raise ValueError('Property citation absent from actual source')
    for obligation in extraction.obligations:
        if obligation.status=='satisfied' and not obligation.sources:
            raise ValueError('Satisfied obligation needs observable evidence')
        for citation in obligation.sources:
            if citation.source_id not in sources or citation.quote not in sources[citation.source_id]:
                raise ValueError('Obligation source absent')
    return {**checks,'partial_observations':'retained','property_source_substrings':'passed',
            'semantic_truth':'unproven; separate uncalibrated model grounding review'}


def withhold_claims(extraction,review,candidate):
    raw=extraction.model_dump()
    by_id={f['id']:f for f in raw['facts']}
    primary={e.name:e.primary_key for e in candidate.entities}
    removed=set()
    for claim in review.unsupported_claims:
        if claim.fact_id not in by_id or claim.property not in by_id[claim.fact_id]['properties']:
            raise ValueError('Grounding reviewer selected an absent property')
        fact=by_id[claim.fact_id]
        if claim.property==primary[fact['type']]:
            removed.add(claim.fact_id)
        fact['properties'].pop(claim.property,None)
        fact['property_sources'].pop(claim.property,None)
    raw['facts']=[f for f in raw['facts'] if f['id'] not in removed]
    raw['edges']=[e for e in raw['edges'] if e['from_id'] not in removed and e['to_id'] not in removed]
    for description in review.reopened_obligations:
        # A semantic rejection is conservative: retain all previously satisfied obligations as unresolved.
        raw['gaps'].append(description)
    if review.reopened_obligations:
        raw['obligations']=[{**o,'status':'unresolved'} for o in raw['obligations']]
    return RevisedExtraction.model_validate(raw)
