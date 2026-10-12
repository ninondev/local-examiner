# Copyright (c) 2026 Ninon
# SPDX-License-Identifier: MPL-2.0
"""Standalone PC/CAP/LE regression tests. All task and proposal fixtures are new and synthetic."""
from __future__ import annotations
import json
import unittest
from local_examiner.textnorm import canon_json, hexify_floats
from local_examiner import proposal_checks as pc
from local_examiner.proposal_checks import analyse_proposal, segment, classify_task_point
from local_examiner.capsule import Capsule, capsule_from_revision, derive_activations, build_capsule, MasteryDecision, CAPSULE_KINDS, criterion_results_from_grade
from local_examiner.local_examiner import examine, narrate, retrieve, score_capsule
from local_examiner import demo
TASK = 'The reader of your proposal is the manager, who can change the hall hours. Write a proposal for the manager.'

def test_PC1_segment_soft_wrap_vs_paragraphs_and_headings():
    txt = 'Introduction\nThe hall is underused in\nthe mornings. Members arrive late.\n\n**Recommendations**\nFirst, extend the morning session.\nSecond, add new clocks.\nPROPOSED BUDGET\n'
    heads, sents = segment(txt)
    assert [h.text for h in heads] == ['Introduction', 'Recommendations', 'PROPOSED BUDGET']
    texts = [s.text for s in sents]
    assert texts[0] == 'The hall is underused in the mornings.'
    assert texts[1] == 'Members arrive late.'
    assert sents[0].para == sents[1].para
    assert sents[2].para != sents[0].para and sents[2].text.startswith('First, extend')
    for s in sents:
        assert txt[s.span.start:s.span.end].split() == s.text.split()

def test_PC2_recommendation_triggers_cover_c1_register():
    txt = 'Current situation\nAt present the hall is underused and the chairs are broken.\n\nRecommendations\nFirst, replace the chairs with wooden benches.\nWe can also add new clocks above the doors.\nIn addition, a booking board would let members reserve a seat.\nIt would be advisable to open after breakfast.\n\nConclusion\nI urge the club to adopt these changes.\n'
    a = analyse_proposal(txt, reader_terms=['manager'])
    triggers = [r.trigger for r in a.recommendations]
    assert 'imperative' in triggers and 'we_can' in triggers and ('it_would_be' in triggers)
    assert any((t in ('declarative_future', 'enumerated_under_heading') for t in triggers))
    assert not any(('urge the club' in r.sentence.text for r in a.recommendations))
    assert len(a.recommendations) == 4

def test_PC3_announcement_is_not_a_recommendation():
    txt = 'The purpose of this proposal is to suggest three changes to the workshop.\n\nFirst, introduce a short evening session.\nSecond, open a second entrance at weekends.\n'
    a = analyse_proposal(txt)
    assert [s.text[:11] for s in a.announcements] == ['The purpose']
    assert len(a.recommendations) == 2

def test_PC4_reason_and_effect_windows():
    txt = 'Current situation\nThe hall closes at five, so members have nowhere to read.\n\nRecommendations\nFirst, extend the evening session, so that members can read after work.\nSecond, buy new lamps for the chairs.\n'
    a = analyse_proposal(txt)
    r1, r2 = a.recommendations
    assert r1.has_effect and r1.effect_marker.lower().startswith('so that')
    assert r1.has_reason and r1.reason_marker
    assert not r2.has_effect
    f = a.by_rule()
    assert f[pc.RULE_RECOMMENDATION_EFFECT].status == 'gap'
    assert f[pc.RULE_RECOMMENDATION_EFFECT].quote.startswith('Second, buy')

def test_PC5_benefit_block_counts_as_effect_for_preceding_recommendations():
    txt = 'Recommendations\nFirst, replace the lamps.\nSecond, install a notice board.\n\nBenefits\nThese changes would encourage members to read. They would also reduce confusion in the hall.\n'
    a = analyse_proposal(txt)
    assert all((r.has_effect for r in a.recommendations))
    assert all(('[benefit block]' in r.effect_marker for r in a.recommendations))

def test_PC6_reader_problem_headings_contractions_wordrange():
    txt = "To: The Manager\nAt present the hall is almost empty at lunchtime.\nYou should extend the session because it's useful. We can't wait.\n"
    a = analyse_proposal(txt, task_text=TASK, word_range=(220, 260))
    f = a.by_rule()
    assert a.reader_terms == ['manager']
    assert f[pc.RULE_READER_ADDRESSED].status == 'ok' and f[pc.RULE_READER_ADDRESSED].quote == 'To: The Manager'
    assert f[pc.RULE_PROBLEM_STATED].status == 'ok' and 'almost empty' in f[pc.RULE_PROBLEM_STATED].quote
    assert f[pc.RULE_HEADINGS_USED].detail['headings'] == ['To: The Manager']
    assert f[pc.RULE_CONTRACTIONS].status == 'gap' and f[pc.RULE_CONTRACTIONS].detail['count'] == 2
    assert f[pc.RULE_WORD_RANGE].status == 'gap'

def test_PC7_task_points_classification_and_coverage():
    pts = ['identify a current problem with the desk area', 'make at least two recommendations', 'give a reason for each recommendation', 'state the expected effect of each recommendation', 'address the desk manager as the reader', 'something about the colour of a lamp']
    kinds = [classify_task_point(p) for p in pts]
    assert kinds[:5] == [('problem', 1), ('recommendations', 2), ('reason', 1), ('effect', 1), ('reader', 1)]
    assert kinds[5][0] == 'unknown'
    txt = 'To: The Desk Manager\nCurrent situation\nThe desk area is unwelcoming because the seats are broken.\n\nRecommendations\nFirst, replace the seats with wooden benches, so that members can wait comfortably.\nSecond, add new lamps beside the desk, which would give members a brighter place to read.\n'
    a = analyse_proposal(txt, task_points=pts, reader_terms=['the desk manager', 'desk manager'])
    status = {t.point[:8]: t.status for t in a.task_points}
    assert status['identify'] == 'covered' and status['make at '] == 'covered'
    assert status['give a r'] == 'covered' and status['state th'] == 'covered'
    assert status['address '] == 'covered' and status['somethin'] == 'unknown'

def test_PC8_deterministic_and_band_free():
    txt = demo.AFTER_HALL
    a1 = analyse_proposal(txt, task_text=demo.TASK_HALL, word_range=(220, 260))
    a2 = analyse_proposal(txt, task_text=demo.TASK_HALL, word_range=(220, 260))
    b1 = canon_json(hexify_floats(a1.to_dict()))
    b2 = canon_json(hexify_floats(a2.to_dict()))
    assert b1 == b2
    dump = json.dumps(a1.to_dict()).lower()
    assert 'band' not in dump and '"score"' not in dump

def test_PC9_synthetic_soft_wrapped_text_counts_sentences_once():
    txt = 'Suggestions\nIn order to help new members, short tours of the workshop\nshould be organised by our club. In addition, a quiet room with a desk\nshould be set up beside the hall. The\nadvantage of this room would be that members could read after a tour.\n'
    a = analyse_proposal(txt)
    assert len(a.sentences) == 3
    assert len(a.recommendations) == 2
    assert a.recommendations[0].has_effect and a.recommendations[0].effect_marker.lower().startswith('in order to')
    assert a.recommendations[1].has_effect

def _cap(**kw) -> Capsule:
    return capsule_from_revision(capability_id=demo.CAPABILITY, task_id='hall-1', prompt_text=demo.TASK_HALL, before_text=demo.BEFORE_HALL, after_text=demo.AFTER_HALL, reader_terms=['the manager', 'manager'], issued_at='2026-09-10T00:00:00+00:00', capsule_id=kw.pop('capsule_id', 'cap-1'), subject_key='subject-1', **kw)

def test_CAP1_digest_is_sha256_of_canonical_unsigned_document():
    import hashlib
    cap = _cap()
    assert cap.signature_algorithm == 'none' and cap.issuer_signature == '' and (cap.signer_key_id == '')
    assert cap.content_digest == hashlib.sha256(cap.canonical_bytes()).hexdigest()
    assert cap.verify_digest()
    assert cap.verify_signature(None) is None
    cap.issuer = 'Someone Else'
    assert not cap.verify_digest()

def test_CAP2_pluggable_signer_and_verifier():

    class FakeSigner:
        key_id = 'k-test'
        algorithm = 'fake-test-only'

        def sign(self, digest: bytes) -> str:
            return 'sig:' + digest.hex()[:12]

    class FakeVerifier:

        def verify(self, digest: bytes, signature: str, key_id: str) -> bool:
            return key_id == 'k-test' and signature == 'sig:' + digest.hex()[:12]
    cap = _cap(signer=FakeSigner())
    assert cap.signature_algorithm == 'fake-test-only' and cap.signer_key_id == 'k-test'
    assert cap.verify_signature(FakeVerifier()) is True
    cap.issuer_signature = 'sig:deadbeef0000'
    assert cap.verify_signature(FakeVerifier()) is False

def test_CAP3_export_import_round_trip_preserves_digest():
    cap = _cap()
    text = cap.export_json()
    back = Capsule.import_json(text)
    assert back.content_digest == cap.content_digest and back.verify_digest()
    assert back.canonical_bytes() == cap.canonical_bytes()
    assert back.task_records[0].revision_pairs and back.rule_activations
    assert 'entitlement' not in text.lower() and 'transaction' not in text.lower()

def test_CAP4_activations_fixed_open_kept():
    before = analyse_proposal(demo.BEFORE_HALL, reader_terms=['manager'], word_range=(220, 260))
    after = analyse_proposal(demo.AFTER_HALL, reader_terms=['manager'], word_range=(220, 260))
    acts, pos, con = derive_activations('t', before, after)
    status = {a.rule_id: a.status for a in acts}
    assert status[pc.RULE_RECOMMENDATION_EFFECT] == 'fixed'
    assert status[pc.RULE_READER_ADDRESSED] == 'fixed'
    assert status[pc.RULE_RECOMMENDATION_COUNT] == 'kept'
    assert status[pc.RULE_WORD_RANGE] == 'open'
    fixed_effect = next((a for a in acts if a.rule_id == pc.RULE_RECOMMENDATION_EFFECT))
    assert fixed_effect.before_quote.startswith('First, extend') and 'so that' in fixed_effect.after_quote
    assert any((c.rule_id == pc.RULE_READER_ADDRESSED and c.after == 'To: The Manager' for c in con))
    assert any((p.rule_id == pc.RULE_RECOMMENDATION_EFFECT for p in pos))

def test_CAP5_kinds_closed_set_and_grade_scores_carried_not_computed():
    assert CAPSULE_KINDS == ('completion', 'revision', 'adjudication')
    with unittest.TestCase().assertRaises(ValueError):
        build_capsule(capability_id='x', task_records=[], rule_activations=[], positive_exemplars=[], contrast_exemplars=[], retrieval_profile={}, mastery=MasteryDecision(False, []), capsule_kind='finished')
    essay = 'A quiet hall. The caretaker works until eight. A bright desk.'
    crs = criterion_results_from_grade({'subscales': [{'name': 'Content', 'band': 4.0, 'evidence': 'The caretaker works until eight.', 'advice': 'keep it'}, {'name': 'Language', 'band': 2.5, 'evidence': 'missing sentence', 'advice': ''}]}, essay)
    assert crs[0].score == 4.0 and crs[0].evidence_spans[0].start == essay.index('The caretaker')
    assert crs[1].evidence_spans[0].end == -1 and crs[1].decision == 'fail'

def test_LE1_plain_mode_when_no_capsule_and_says_so():
    rep = examine(demo.NEW_WORKSHOP, task_text=demo.TASK_WORKSHOP, capability_id=demo.CAPABILITY, capsules=[], reader_terms=['events officer', 'officer'])
    assert rep.mode == 'plain' and 'plain mode' in rep.note
    assert rep.usage.retrieved_capsule_ids == [] and rep.personal == [] and (rep.kept == [])
    assert any((g['rule_id'] == pc.RULE_RECOMMENDATION_EFFECT for g in rep.generic_gaps))

def test_LE2_retrieval_filters_by_rubric_and_scores_capability_first():
    same = _cap(capsule_id='same-cap')
    other = _cap(capsule_id='other-cap', rubric_id='other.writing')
    diff_cap = _cap(capsule_id='diff-capability')
    diff_cap.capability_id = 'report.other'
    diff_cap.seal()
    got = retrieve([diff_cap, other, same], capability_id=demo.CAPABILITY, genre='proposal', reader_terms=['officer'], k=3)
    assert [c.capsule_id for c in got][0] == 'same-cap'
    assert 'other-cap' not in [c.capsule_id for c in got]
    assert score_capsule(same, capability_id=demo.CAPABILITY, genre='proposal', reader_terms=['manager'], rubric_id='cambridge.c1_advanced.writing') == 4 + 2 + 1 + 1

def test_LE3_recurring_gap_links_prior_fix_to_current_evidence():
    cap = _cap()
    rep = examine(demo.NEW_WORKSHOP, task_text=demo.TASK_WORKSHOP, capability_id=demo.CAPABILITY, capsules=[cap], reader_terms=['the events officer', 'events officer', 'officer'])
    assert rep.mode == 'capsule'
    eff = next((p for p in rep.personal if p.rule_id == pc.RULE_RECOMMENDATION_EFFECT))
    assert eff.current_quote.startswith('First, open a late session')
    assert eff.prior_task_id == 'hall-1'
    assert eff.prior_before.startswith('First, extend') and 'so that' in eff.prior_after
    assert eff.next_step
    assert rep.usage.retrieved_capsule_ids == ['cap-1']
    assert f'cap-1:{pc.RULE_RECOMMENDATION_EFFECT}' in rep.usage.used_exemplar_ids
    assert any((fs['rule_id'] == pc.RULE_RECOMMENDATION_EFFECT and fs['prior_outcome'] == 'fixed' for fs in rep.few_shot))

def test_LE4_kept_rule_not_reminded_again():
    cap = _cap()
    rep = examine(demo.NEW_WORKSHOP, task_text=demo.TASK_WORKSHOP, capability_id=demo.CAPABILITY, capsules=[cap], reader_terms=['the events officer', 'events officer', 'officer'])
    assert [k.rule_id for k in rep.kept] == [pc.RULE_READER_ADDRESSED]
    assert not any((g['rule_id'] == pc.RULE_READER_ADDRESSED for g in rep.generic_gaps))
    assert not any((g['rule_id'] == pc.RULE_RECOMMENDATION_EFFECT for g in rep.generic_gaps))

def test_LE5_reports_are_deterministic_and_band_free():
    cap = _cap()
    kw = dict(task_text=demo.TASK_WORKSHOP, capability_id=demo.CAPABILITY, capsules=[cap], reader_terms=['the events officer', 'events officer', 'officer'])
    r1 = examine(demo.NEW_WORKSHOP, **kw)
    r2 = examine(demo.NEW_WORKSHOP, **kw)
    assert canon_json(hexify_floats(r1.to_dict())) == canon_json(hexify_floats(r2.to_dict()))
    text = narrate(r1)
    assert 'band' not in text.lower() and 'score' not in text.lower()
    assert 'last time (hall-1)' in text and 'Kept from last time' in text

def test_LE6_demo_side_by_side_shows_capsule_advantage():
    out = demo.run_demo()
    assert 'PLAIN mode' in out and 'CAPSULE mode' in out
    plain, capsule = out.split('CAPSULE mode')
    assert 'Recurring gaps' not in plain and 'Recurring gaps' in capsule
    assert 'you had' in capsule and 'fixed it to' in capsule

def load_tests(loader, tests, pattern):
    cases = [unittest.FunctionTestCase(value) for name, value in globals().items()
             if name.startswith("test_") and callable(value)]
    return unittest.TestSuite(cases)
