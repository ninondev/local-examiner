# Copyright (c) 2026 Ninon
# SPDX-License-Identifier: MIT
"""Retrieve prior revisions and link recurring rule gaps to evidence in the current proposal."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any
from local_examiner.capsule import Capsule
from local_examiner.proposal_checks import ProposalAnalysis, analyse_proposal, RULE_IDS, SEVERITY, RULE_RECOMMENDATION_COUNT, RULE_RECOMMENDATION_REASON, RULE_RECOMMENDATION_EFFECT, RULE_PROBLEM_STATED, RULE_READER_ADDRESSED, RULE_FUTURE_ORIENTATION, RULE_HEADINGS_USED, RULE_CONTRACTIONS, RULE_WORD_RANGE
LOCAL_EXAMINER_VERSION = 'le-1'
NEXT_STEP = {RULE_RECOMMENDATION_COUNT: 'Add a second recommendation as its own sentence, starting with what you want the reader to do.', RULE_RECOMMENDATION_REASON: 'After the recommendation, add one sentence that names the current problem it answers (because / since / at present…).', RULE_RECOMMENDATION_EFFECT: "Finish the recommendation with the result you expect for the reader's people (would allow / so that / which would…).", RULE_PROBLEM_STATED: 'Open with one sentence that names what is wrong now, before any recommendation.', RULE_READER_ADDRESSED: 'Name the reader once (To: / Dear …) and speak to them directly at least twice.', RULE_FUTURE_ORIENTATION: 'Turn the recommendation sections towards what would change, not what happened.', RULE_HEADINGS_USED: 'Give each section a short heading so the reader can find each recommendation.', RULE_CONTRACTIONS: 'Write the full forms (do not / it is) in a proposal.', RULE_WORD_RANGE: 'Bring the length inside the task range.'}

@dataclass
class PersonalFinding:
    rule_id: str
    severity: int
    current_quote: str
    current_span: tuple[int, int] | None
    capsule_id: str
    prior_task_id: str
    prior_before: str
    prior_after: str
    next_step: str
    current_note: str = ''

@dataclass
class KeptRule:
    rule_id: str
    capsule_id: str
    current_quote: str

@dataclass
class UsageRecord:
    retrieved_capsule_ids: list[str]
    activated_rule_ids: list[str]
    used_exemplar_ids: list[str]

@dataclass
class ExaminerReport:
    version: str
    mode: str
    analysis: ProposalAnalysis
    generic_gaps: list[dict[str, Any]]
    personal: list[PersonalFinding]
    kept: list[KeptRule]
    next_focus: str | None
    usage: UsageRecord
    few_shot: list[dict[str, str]]
    note: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d['analysis'] = self.analysis.to_dict()
        return d

def score_capsule(cap: Capsule, *, capability_id: str, genre: str, reader_terms: list[str], rubric_id: str) -> int:
    p = cap.retrieval_profile or {}
    score = 0
    if cap.capability_id == capability_id:
        score += 4
    if p.get('genre') == genre:
        score += 2
    if cap.rubric_id == rubric_id:
        score += 1
    shared = set((t.lower() for t in p.get('reader_terms') or [])) & set((t.lower() for t in reader_terms))
    score += min(2, len(shared))
    return score

def retrieve(capsules: list[Capsule], *, capability_id: str, genre: str, reader_terms: list[str], rubric_id: str='cambridge.c1_advanced.writing', k: int=3, min_score: int=3) -> list[Capsule]:
    """Filter by rubric, then sort by score, descending timestamp string, and capsule ID.
Use a consistent UTC ISO timestamp format when chronological order matters."""
    scored = [(score_capsule(c, capability_id=capability_id, genre=genre, reader_terms=reader_terms, rubric_id=rubric_id), c) for c in capsules if c.rubric_id == rubric_id]
    scored = [(s, c) for s, c in scored if s >= min_score]
    scored.sort(key=lambda sc: (-sc[0], sc[1].issued_at, sc[1].capsule_id), reverse=False)
    scored.sort(key=lambda sc: (-sc[0], _neg_time(sc[1].issued_at), sc[1].capsule_id))
    return [c for _, c in scored[:k]]

def _neg_time(s: str) -> str:
    return ''.join((chr(1114111 - ord(ch)) for ch in s))

def activated_rules(capsules: list[Capsule]) -> dict[str, list[tuple[Capsule, Any]]]:
    """Collect prior fixed or open rule records in retrieval order."""
    out: dict[str, list[tuple[Capsule, Any]]] = {}
    for c in capsules:
        for a in c.rule_activations:
            if a.status in ('fixed', 'open'):
                out.setdefault(a.rule_id, []).append((c, a))
    return out

def _best_prior(entries: list[tuple[Capsule, Any]]) -> tuple[Capsule, Any]:
    """Prefer fixed records, then the latest timestamp string and capsule ID."""
    fixed = [e for e in entries if e[1].status == 'fixed']
    pool = fixed or entries
    pool = sorted(pool, key=lambda e: (_neg_time(e[0].issued_at), e[0].capsule_id))
    return pool[0]

def examine(text: str, *, task_text: str='', capability_id: str, genre: str='proposal', capsules: list[Capsule] | None=None, task_points: list[str] | None=None, reader_terms: list[str] | None=None, word_range: tuple[int, int] | None=(220, 260), min_recommendations: int=2, rubric_id: str='cambridge.c1_advanced.writing', k: int=3) -> ExaminerReport:
    analysis = analyse_proposal(text, task_text=task_text, task_points=task_points, min_recommendations=min_recommendations, word_range=word_range, reader_terms=reader_terms)
    generic = [{'rule_id': f.rule_id, 'severity': f.severity, 'quote': f.quote, 'note': f.note, 'span': [f.span.start, f.span.end] if f.span else None} for f in analysis.findings if f.status == 'gap']
    terms = list(reader_terms or analysis.reader_terms)
    chosen = retrieve(capsules or [], capability_id=capability_id, genre=genre, reader_terms=terms, rubric_id=rubric_id, k=k)
    if not chosen:
        return ExaminerReport(LOCAL_EXAMINER_VERSION, 'plain', analysis, generic, [], [], _first_focus(generic), UsageRecord([], [], []), [], 'No relevant capsule for this capability; working in plain mode (no memory of this learner).')
    acts = activated_rules(chosen)
    by_rule = analysis.by_rule()
    personal: list[PersonalFinding] = []
    kept: list[KeptRule] = []
    used_ex: list[str] = []
    few_shot: list[dict[str, str]] = []
    for rule_id in RULE_IDS:
        if rule_id not in acts:
            continue
        f = by_rule.get(rule_id)
        if f is None:
            continue
        cap, a = _best_prior(acts[rule_id])
        if f.status == 'gap':
            personal.append(PersonalFinding(rule_id, SEVERITY[rule_id], f.quote, (f.span.start, f.span.end) if f.span else None, cap.capsule_id, a.task_id, a.before_quote, a.after_quote, NEXT_STEP.get(rule_id, ''), f.note))
            ex_id = f'{cap.capsule_id}:{rule_id}'
            used_ex.append(ex_id)
            few_shot.append({'rule_id': rule_id, 'prior_task_id': a.task_id, 'prior_problem': a.before_quote, 'prior_fix': a.after_quote, 'prior_outcome': 'fixed' if a.status == 'fixed' else 'still open', 'current_evidence': f.quote})
        elif f.status == 'ok' and a.status == 'fixed':
            kept.append(KeptRule(rule_id, cap.capsule_id, f.quote))
    kept_ids = {kr.rule_id for kr in kept}
    personal_ids = {pf.rule_id for pf in personal}
    generic_rest = [g for g in generic if g['rule_id'] not in personal_ids and g['rule_id'] not in kept_ids]
    usage = UsageRecord([c.capsule_id for c in chosen], sorted(acts.keys()), used_ex)
    focus = _first_focus([asdict(p) for p in personal]) or _first_focus(generic_rest)
    return ExaminerReport(LOCAL_EXAMINER_VERSION, 'capsule', analysis, generic_rest, personal, kept, focus, usage, few_shot, f'{len(chosen)} capsule(s) retrieved; {len(personal)} recurring gap(s), {len(kept)} rule(s) kept.')

def _first_focus(items: list[dict[str, Any]]) -> str | None:
    if not items:
        return None
    best = sorted(items, key=lambda g: (-int(g.get('severity', 0)), RULE_IDS.index(g['rule_id']) if g['rule_id'] in RULE_IDS else 99))[0]
    return best['rule_id']

def narrate(report: ExaminerReport, *, essay: str='') -> str:
    lines: list[str] = []
    lines.append(f'[mode: {report.mode}] {report.note}')
    if report.personal:
        lines.append('Recurring gaps (from your own precedents):')
        for p in report.personal:
            now = f'"{_short(p.current_quote)}"' if p.current_quote else p.current_note
            lines.append(f'  - {p.rule_id}: this time → {now}')
            if p.prior_before or p.prior_after:
                lines.append(f'      last time ({p.prior_task_id}) you had "{_short(p.prior_before)}" and fixed it to "{_short(p.prior_after)}"')
            lines.append(f'      next step: {p.next_step}')
    if report.kept:
        lines.append('Kept from last time (no reminder needed): ' + ', '.join((k.rule_id for k in report.kept)))
    if report.generic_gaps:
        lines.append('Other gaps located in the text:')
        for g in report.generic_gaps:
            q = f''' → "{_short(g['quote'])}"''' if g.get('quote') else ''
            lines.append(f"  - {g['rule_id']}: {g['note']}{q}")
    if report.next_focus:
        lines.append(f'Focus next: {report.next_focus}')
    lines.append(f'usage: retrieved={report.usage.retrieved_capsule_ids} activated={report.usage.activated_rule_ids} exemplars={report.usage.used_exemplar_ids}')
    return '\n'.join(lines)

def _short(s: str, n: int=90) -> str:
    s = (s or '').replace('\n', ' ')
    return s if len(s) <= n else s[:n - 1] + '…'
