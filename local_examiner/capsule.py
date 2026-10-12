# Copyright (c) 2026 Ninon
# SPDX-License-Identifier: MPL-2.0
"""Revision records, canonical capsule bytes, content digests, and optional signing hooks."""
from __future__ import annotations
import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Protocol
from local_examiner.textnorm import canon_json, hexify_floats
from local_examiner.proposal_checks import ProposalAnalysis, analyse_proposal, PROPOSAL_CHECKS_VERSION
CAPSULE_SCHEMA_VERSION = 1
CAPSULE_KINDS = ('completion', 'revision', 'adjudication')
ASSISTANCE_MODES = ('independent', 'declared_independent', 'assisted')
DECISIONS = ('pass', 'fail', 'undecidable')
SIGNATURE_FIELDS = ('signer_key_id', 'signature_algorithm', 'issuer_signature')

class Signer(Protocol):
    key_id: str
    algorithm: str

    def sign(self, digest: bytes) -> str:
        ...

class Verifier(Protocol):

    def verify(self, digest: bytes, signature: str, key_id: str) -> bool:
        ...

@dataclass
class EvidenceSpan:
    start: int
    end: int
    quote: str

@dataclass
class CriterionResult:
    criterion_id: str
    score: float
    score_interval: list[float]
    decision: str
    evidence_spans: list[EvidenceSpan]
    explanation: str
    advice: str = ''
    discriminator: str = ''

@dataclass
class ObservableCheck:
    rule_id: str
    status: str
    quote: str
    note: str
    start: int | None = None
    end: int | None = None

@dataclass
class RevisionPair:
    rule_id: str
    before: str
    after: str
    intent: str
    round_no: int = 1

@dataclass
class TransferResult:
    kind: str
    task_key: str
    decision: str
    note: str = ''

@dataclass
class TaskRecord:
    task_id: str
    task_hash: str
    prompt_snapshot: str
    task_origin: str
    unseen_scope: str
    constraints: dict[str, Any]
    response_snapshot: str
    started_at: str
    submitted_at: str
    duration_seconds: int
    assistance_mode: str
    input_provenance: dict[str, Any]
    criterion_results: list[CriterionResult]
    observable_checks: list[ObservableCheck]
    change_card: str | None = None
    reader_reconstruction: str | None = None
    revision_pairs: list[RevisionPair] = field(default_factory=list)
    transfer_results: list[TransferResult] = field(default_factory=list)

@dataclass
class RuleActivation:
    rule_id: str
    status: str
    task_id: str
    before_quote: str = ''
    after_quote: str = ''
    note: str = ''

@dataclass
class Exemplar:
    rule_id: str
    task_id: str
    quote: str
    context: str = ''

@dataclass
class ContrastExemplar:
    rule_id: str
    task_id: str
    before: str
    after: str
    intent: str = ''

@dataclass
class MasteryDecision:
    achieved: bool
    grounds: list[str]

@dataclass
class Capsule:
    schema_version: int
    capsule_id: str
    capsule_kind: str
    capability_id: str
    contract_version: str
    issuer: str
    subject_key: str
    issued_at: str
    rubric_id: str
    rubric_version: str
    evaluator_version: str
    task_records: list[TaskRecord]
    mastery_decision: MasteryDecision
    retrieval_profile: dict[str, Any]
    positive_exemplars: list[Exemplar]
    contrast_exemplars: list[ContrastExemplar]
    rule_activations: list[RuleActivation]
    lineage: list[str]
    content_digest: str = ''
    signer_key_id: str = ''
    signature_algorithm: str = 'none'
    issuer_signature: str = ''

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def unsigned_dict(self) -> dict[str, Any]:
        d = self.to_dict()
        for k in SIGNATURE_FIELDS + ('content_digest',):
            d.pop(k, None)
        return d

    def canonical_bytes(self) -> bytes:
        return canon_json(hexify_floats(self.unsigned_dict()))

    def compute_digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    def seal(self, signer: Signer | None=None) -> 'Capsule':
        """Update the content digest and sign it if a signer is supplied."""
        self.content_digest = self.compute_digest()
        if signer is None:
            self.signer_key_id = ''
            self.signature_algorithm = 'none'
            self.issuer_signature = ''
        else:
            self.signer_key_id = signer.key_id
            self.signature_algorithm = signer.algorithm
            self.issuer_signature = signer.sign(bytes.fromhex(self.content_digest))
        return self

    def verify_digest(self) -> bool:
        return bool(self.content_digest) and self.content_digest == self.compute_digest()

    def verify_signature(self, verifier: Verifier | None) -> bool | None:
        """Return None when unsigned or when no verifier is supplied. Check the digest separately."""
        if self.signature_algorithm == 'none' or not self.issuer_signature or verifier is None:
            return None
        return verifier.verify(bytes.fromhex(self.content_digest), self.issuer_signature, self.signer_key_id)

    def export_json(self) -> str:
        """Export readable JSON with sorted keys and floats encoded as binary64 hex."""
        return json.dumps(hexify_floats(self.to_dict()), ensure_ascii=False, sort_keys=True, indent=1)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> 'Capsule':
        d = _unhexify(d)
        trs = [TaskRecord(**{**t, 'criterion_results': [CriterionResult(**{**c, 'evidence_spans': [EvidenceSpan(**e) for e in c['evidence_spans']]}) for c in t['criterion_results']], 'observable_checks': [ObservableCheck(**o) for o in t['observable_checks']], 'revision_pairs': [RevisionPair(**r) for r in t.get('revision_pairs', [])], 'transfer_results': [TransferResult(**x) for x in t.get('transfer_results', [])]}) for t in d['task_records']]
        return cls(schema_version=d['schema_version'], capsule_id=d['capsule_id'], capsule_kind=d['capsule_kind'], capability_id=d['capability_id'], contract_version=d['contract_version'], issuer=d['issuer'], subject_key=d['subject_key'], issued_at=d['issued_at'], rubric_id=d['rubric_id'], rubric_version=d['rubric_version'], evaluator_version=d['evaluator_version'], task_records=trs, mastery_decision=MasteryDecision(**d['mastery_decision']), retrieval_profile=d['retrieval_profile'], positive_exemplars=[Exemplar(**e) for e in d['positive_exemplars']], contrast_exemplars=[ContrastExemplar(**e) for e in d['contrast_exemplars']], rule_activations=[RuleActivation(**r) for r in d['rule_activations']], lineage=list(d['lineage']), content_digest=d.get('content_digest', ''), signer_key_id=d.get('signer_key_id', ''), signature_algorithm=d.get('signature_algorithm', 'none'), issuer_signature=d.get('issuer_signature', ''))

    @classmethod
    def import_json(cls, text: str) -> 'Capsule':
        return cls.from_dict(json.loads(text))

def _unhexify(obj: Any) -> Any:
    from local_examiner.textnorm import f64_unhex
    if isinstance(obj, dict):
        if set(obj.keys()) == {'~f64'}:
            return f64_unhex(obj['~f64'])
        return {k: _unhexify(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_unhexify(v) for v in obj]
    return obj

def task_hash(prompt_text: str) -> str:
    return hashlib.sha256(prompt_text.strip().encode('utf-8')).hexdigest()

def observable_checks_from(analysis: ProposalAnalysis) -> list[ObservableCheck]:
    return [ObservableCheck(f.rule_id, f.status, f.quote, f.note, f.span.start if f.span else None, f.span.end if f.span else None) for f in analysis.findings]

def criterion_results_from_grade(grade: dict[str, Any], essay: str) -> list[CriterionResult]:
    """Carry caller-supplied bands and locate their evidence. This does not grade text.

The stored interval is a fixed band +/- 1 window, not a measured confidence interval."""
    out: list[CriterionResult] = []
    for s in grade.get('subscales', []):
        quote = (s.get('evidence') or '').strip()
        spans: list[EvidenceSpan] = []
        if quote:
            i = essay.find(quote)
            spans.append(EvidenceSpan(i, i + len(quote) if i >= 0 else -1, quote))
        band = float(s.get('band', 0.0))
        out.append(CriterionResult(criterion_id=str(s.get('name', '')), score=band, score_interval=[max(0.0, band - 1.0), min(5.0, band + 1.0)], decision='pass' if band >= 3.0 else 'fail', evidence_spans=spans, explanation=str(s.get('advice') or ''), advice=str(s.get('advice') or ''), discriminator=str(s.get('discriminator') or '')))
    return out

def derive_activations(task_id: str, before: ProposalAnalysis | None, after: ProposalAnalysis, before_text: str='', after_text: str='') -> tuple[list[RuleActivation], list[Exemplar], list[ContrastExemplar]]:
    """Record gap to ok as fixed, remaining gaps as open, and unchanged ok rules as kept."""
    acts: list[RuleActivation] = []
    pos: list[Exemplar] = []
    con: list[ContrastExemplar] = []
    b = before.by_rule() if before else {}
    for f in after.findings:
        prev = b.get(f.rule_id)
        if prev is not None and prev.status == 'gap' and (f.status == 'ok'):
            acts.append(RuleActivation(f.rule_id, 'fixed', task_id, prev.quote, f.quote, f'was: {prev.note}; now: {f.note}'))
            if f.quote:
                pos.append(Exemplar(f.rule_id, task_id, f.quote, f.note))
            con.append(ContrastExemplar(f.rule_id, task_id, prev.quote, f.quote, 'revision'))
        elif f.status == 'gap':
            acts.append(RuleActivation(f.rule_id, 'open', task_id, prev.quote if prev else '', f.quote, f.note))
        elif f.status == 'ok' and (prev is None or prev.status == 'ok'):
            acts.append(RuleActivation(f.rule_id, 'kept', task_id, '', f.quote, f.note))
    return (acts, pos, con)

def build_capsule(*, capability_id: str, task_records: list[TaskRecord], rule_activations: list[RuleActivation], positive_exemplars: list[Exemplar], contrast_exemplars: list[ContrastExemplar], retrieval_profile: dict[str, Any], mastery: MasteryDecision, issuer: str='local', subject_key: str='', rubric_id: str='cambridge.c1_advanced.writing', rubric_version: str='1', evaluator_version: str='', contract_version: str='1', capsule_kind: str='completion', lineage: list[str] | None=None, issued_at: str | None=None, capsule_id: str | None=None, signer: Signer | None=None) -> Capsule:
    if capsule_kind not in CAPSULE_KINDS:
        raise ValueError(f'unknown capsule_kind {capsule_kind}')
    cap = Capsule(schema_version=CAPSULE_SCHEMA_VERSION, capsule_id=capsule_id or str(uuid.uuid4()), capsule_kind=capsule_kind, capability_id=capability_id, contract_version=contract_version, issuer=issuer, subject_key=subject_key, issued_at=issued_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat(), rubric_id=rubric_id, rubric_version=rubric_version, evaluator_version=evaluator_version or f'{PROPOSAL_CHECKS_VERSION}', task_records=task_records, mastery_decision=mastery, retrieval_profile=dict(retrieval_profile), positive_exemplars=list(positive_exemplars), contrast_exemplars=list(contrast_exemplars), rule_activations=list(rule_activations), lineage=list(lineage or []))
    return cap.seal(signer)

def capsule_from_revision(*, capability_id: str, task_id: str, prompt_text: str, before_text: str, after_text: str, task_origin: str='local', genre: str='proposal', reader_terms: list[str] | None=None, task_points: list[str] | None=None, word_range: tuple[int, int]=(220, 260), grade_after: dict[str, Any] | None=None, started_at: str='', submitted_at: str='', duration_seconds: int=0, assistance_mode: str='assisted', **kw) -> Capsule:
    """Build a practice capsule from a before/after pair. Supply issued_at and capsule_id
for repeatable bytes; omitted values use the current UTC time and a random UUID."""
    before = analyse_proposal(before_text, task_text=prompt_text, task_points=task_points, word_range=word_range, reader_terms=reader_terms)
    after = analyse_proposal(after_text, task_text=prompt_text, task_points=task_points, word_range=word_range, reader_terms=reader_terms)
    acts, pos, con = derive_activations(task_id, before, after, before_text, after_text)
    pairs = [RevisionPair(c.rule_id, c.before, c.after, c.intent) for c in con]
    rec = TaskRecord(task_id=task_id, task_hash=task_hash(prompt_text), prompt_snapshot=prompt_text, task_origin=task_origin, unseen_scope='practice', constraints={'words': list(word_range), 'genre': genre}, response_snapshot=after_text, started_at=started_at, submitted_at=submitted_at, duration_seconds=duration_seconds, assistance_mode=assistance_mode, input_provenance={'typed': True}, criterion_results=criterion_results_from_grade(grade_after or {}, after_text), observable_checks=observable_checks_from(after), revision_pairs=pairs)
    profile = {'capability_id': capability_id, 'genre': genre, 'reader_terms': list(reader_terms or after.reader_terms), 'open_rules': sorted({a.rule_id for a in acts if a.status == 'open'}), 'fixed_rules': sorted({a.rule_id for a in acts if a.status == 'fixed'}), 'kept_rules': sorted({a.rule_id for a in acts if a.status == 'kept'}), 'checks_version': PROPOSAL_CHECKS_VERSION}
    return build_capsule(capability_id=capability_id, task_records=[rec], rule_activations=acts, positive_exemplars=pos, contrast_exemplars=con, retrieval_profile=profile, mastery=MasteryDecision(False, ['revision capsule: practice only, no mastery ruling']), capsule_kind='revision', **kw)
