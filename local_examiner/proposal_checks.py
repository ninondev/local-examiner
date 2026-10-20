# Copyright (c) 2026 Ninon
# SPDX-License-Identifier: MIT
"""Rule-based checks for English proposals. Findings include source character offsets.

These heuristics do not award exam scores or decide writing quality."""

from __future__ import annotations
import re
from dataclasses import dataclass, field, asdict
from typing import Any

PROPOSAL_CHECKS_VERSION = 'pc-1'
RULE_RECOMMENDATION_COUNT = 'proposal.recommendation_count'
RULE_RECOMMENDATION_REASON = 'proposal.recommendation_has_reason'
RULE_RECOMMENDATION_EFFECT = 'proposal.recommendation_has_effect'
RULE_PROBLEM_STATED = 'proposal.problem_stated'
RULE_READER_ADDRESSED = 'proposal.reader_addressed'
RULE_FUTURE_ORIENTATION = 'proposal.future_orientation'
RULE_HEADINGS_USED = 'proposal.headings_used'
RULE_CONTRACTIONS = 'proposal.contractions'
RULE_WORD_RANGE = 'proposal.word_range'
RULE_LETTER_FRAME = 'proposal.letter_frame'
RULE_IDS: tuple[str, ...] = (
    RULE_RECOMMENDATION_COUNT,
    RULE_RECOMMENDATION_REASON,
    RULE_RECOMMENDATION_EFFECT,
    RULE_PROBLEM_STATED,
    RULE_READER_ADDRESSED,
    RULE_FUTURE_ORIENTATION,
    RULE_HEADINGS_USED,
    RULE_CONTRACTIONS,
    RULE_WORD_RANGE,
    RULE_LETTER_FRAME,
)
SEVERITY = {
    RULE_RECOMMENDATION_COUNT: 3,
    RULE_RECOMMENDATION_REASON: 2,
    RULE_RECOMMENDATION_EFFECT: 2,
    RULE_PROBLEM_STATED: 3,
    RULE_READER_ADDRESSED: 2,
    RULE_FUTURE_ORIENTATION: 1,
    RULE_HEADINGS_USED: 1,
    RULE_CONTRACTIONS: 1,
    RULE_WORD_RANGE: 1,
    RULE_LETTER_FRAME: 1,
}


@dataclass(frozen=True)
class Span:
    start: int
    end: int

    def slice(self, text: str) -> str:
        return text[self.start : self.end]


@dataclass(frozen=True)
class Sentence:
    index: int
    para: int
    span: Span
    text: str
    section: int = 0


@dataclass(frozen=True)
class Heading:
    span: Span
    text: str


@dataclass
class Recommendation:
    """A recommendation and up to three following sentences in the same paragraph."""

    index: int
    sentence: Sentence
    unit: Span
    trigger: str
    trigger_span: Span
    reason: Span | None = None
    effect: Span | None = None
    reason_marker: str = ''
    effect_marker: str = ''

    @property
    def has_reason(self) -> bool:
        return self.reason is not None

    @property
    def has_effect(self) -> bool:
        return self.effect is not None


@dataclass
class Finding:
    rule_id: str
    status: str
    severity: int
    span: Span | None
    quote: str
    note: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskPointResult:
    point: str
    kind: str
    status: str
    evidence: list[Span]
    note: str


@dataclass
class ProposalAnalysis:
    version: str
    word_count: int
    headings: list[Heading]
    sentences: list[Sentence]
    recommendations: list[Recommendation]
    findings: list[Finding]
    task_points: list[TaskPointResult]
    reader_terms: list[str]
    announcements: list[Sentence] = field(default_factory=list)

    def gaps(self) -> list[Finding]:
        return [f for f in self.findings if f.status == 'gap']

    def by_rule(self) -> dict[str, Finding]:
        return {f.rule_id: f for f in self.findings}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_ABBREV = (
    'e.g.',
    'i.e.',
    'etc.',
    'mr.',
    'mrs.',
    'ms.',
    'dr.',
    'prof.',
    'vs.',
    'no.',
    'st.',
    'approx.',
)
_HEADING_MAX_WORDS = 8
_HEADING_KEYWORDS = (
    'introduction',
    'recommendation',
    'recommendations',
    'suggestion',
    'suggestions',
    'proposal',
    'proposals',
    'conclusion',
    'background',
    'problem',
    'problems',
    'benefit',
    'benefits',
    'aim',
    'aims',
    'purpose',
    'current situation',
    'summary',
    'remarks',
    'issues',
    'to:',
    'from:',
    'subject:',
    're:',
    'title:',
    'date:',
)
_TERMINAL = '.!?'
_MD_WRAP = re.compile('^[\\s*_#]+|[\\s*_:]+$')


def _is_heading(line: str) -> bool:
    s = _MD_WRAP.sub('', line.strip())
    if not s or len(s.split()) > _HEADING_MAX_WORDS:
        return False
    if line.strip().rstrip('*_ ').endswith(':') and len(s.split()) <= _HEADING_MAX_WORDS:
        return True
    low = s.lower()
    if low.endswith(':') or any(
        (low.startswith(k) for k in ('to:', 'from:', 'subject:', 're:', 'date:'))
    ):
        return True
    if s[-1] in '.!?,;' and (not low.endswith('etc.')):
        return False
    letters = [c for c in s if c.isalpha()]
    if letters and all((c.isupper() for c in letters)):
        return True
    if any((k in low for k in _HEADING_KEYWORDS)):
        return True
    words = [w for w in re.split('\\s+', s) if w]
    caps = sum((1 for w in words if w[:1].isupper()))
    return 1 <= len(words) <= 5 and caps >= max(1, (len(words) + 1) // 2)


def _blocks(text: str) -> tuple[list[Heading], list[tuple[int, int]]]:
    """Merge soft-wrapped lines; terminal punctuation followed by an uppercase line starts a block."""
    headings: list[Heading] = []
    blocks: list[tuple[int, int]] = []
    cur: tuple[int, int] | None = None
    prev_terminal = True
    i = 0
    n = len(text)
    while i <= n:
        nl = text.find('\n', i)
        end = n if nl < 0 else nl
        line = text[i:end]
        stripped = line.strip()
        if not stripped:
            if cur:
                blocks.append(cur)
                cur = None
            prev_terminal = True
        elif _is_heading(line):
            if cur:
                blocks.append(cur)
                cur = None
            lead = len(line) - len(line.lstrip())
            headings.append(
                Heading(Span(i + lead, i + lead + len(stripped)), _MD_WRAP.sub('', stripped))
            )
            prev_terminal = True
        else:
            lead = len(line) - len(line.lstrip())
            st = i + lead
            en = i + lead + len(stripped)
            starts_upper = stripped[:1].isupper()
            if cur and (not (prev_terminal and starts_upper)):
                cur = (cur[0], en)
            else:
                if cur:
                    blocks.append(cur)
                cur = (st, en)
            prev_terminal = stripped[-1] in _TERMINAL + '"\'”’)'
        if nl < 0:
            break
        i = nl + 1
    if cur:
        blocks.append(cur)
    return (headings, blocks)


def segment(text: str) -> tuple[list[Heading], list[Sentence]]:
    """Split headings and sentences and retain character offsets in the original text."""
    headings, blocks = _blocks(text)
    sentences: list[Sentence] = []
    for para, (bs, be) in enumerate(blocks):
        section = sum((1 for h in headings if h.span.end <= bs))
        body = text[bs:be]
        start = 0
        i = 0
        while i < len(body):
            if body[i] in _TERMINAL:
                j = i + 1
                while j < len(body) and body[j] in _TERMINAL + '"\'”’)':
                    j += 1
                tail = body[start:j].strip().lower()
                is_abbrev = any((tail.endswith(a) for a in _ABBREV))
                at_end = j >= len(body)
                nxt = body[j : j + 2]
                boundary = at_end or (
                    nxt[:1].isspace()
                    and (len(nxt) < 2 or nxt[1:2].isupper() or nxt[1:2] in '"\'“‘(')
                )
                if boundary and (not is_abbrev):
                    seg = body[start:j]
                    lead = len(seg) - len(seg.lstrip())
                    if seg.strip():
                        sentences.append(
                            Sentence(
                                len(sentences),
                                para,
                                Span(bs + start + lead, bs + j),
                                re.sub('\\s+', ' ', seg.strip()),
                                section,
                            )
                        )
                    start = j
                i = j
                continue
            i += 1
        rest = body[start:]
        if rest.strip():
            lead = len(rest) - len(rest.lstrip())
            sentences.append(
                Sentence(
                    len(sentences),
                    para,
                    Span(bs + start + lead, be),
                    re.sub('\\s+', ' ', rest.strip()),
                    section,
                )
            )
    return (headings, sentences)


_ACTION_VERBS = 'introduc(?:e|ed|ing)|offer(?:ed|ing)?|extend(?:ed|ing)?|creat(?:e|ed|ing)|set(?:ting)?\\s+up|provid(?:e|ed|ing)|install(?:ed|ing)?|organi[sz](?:e|ed|ing)|open(?:ed|ing)?|hir(?:e|ed|ing)|start(?:ed|ing)?|launch(?:ed|ing)?|run(?:ning)?|h[oe]ld(?:ing)?|add(?:ed|ing)?|replac(?:e|ed|ing)|reduc(?:e|ed|ing)|increas(?:e|ed|ing)|allow(?:ed|ing)?|invest(?:ed|ing)?|consider(?:ed|ing)?|invit(?:e|ed|ing)|arrang(?:e|ed|ing)|build(?:ing)?|built|buy(?:ing)?|bought|put(?:ting)?|mov(?:e|ed|ing)|chang(?:e|ed|ing)|improv(?:e|ed|ing)|mak(?:e|ing)|made|giv(?:e|en|ing)|us(?:e|ed|ing)|develop(?:ed|ing)?|design(?:ed|ing)?|includ(?:e|ed|ing)|encourag(?:e|ed|ing)|promot(?:e|ed|ing)|host(?:ed|ing)?|train(?:ed|ing)?|employ(?:ed|ing)?|appoint(?:ed|ing)?|establish(?:ed|ing)?|schedul(?:e|ed|ing)|send(?:ing)?|sent|show(?:n|ing)?|outlin(?:e|ed|ing)|focus(?:ed|ing)?|refer|ask(?:ed|ing)?|afford|combin(?:e|ed|ing)|split|divid(?:e|ed|ing)|limit(?:ed|ing)?|ban(?:ned|ning)?|requir(?:e|ed|ing)|produc(?:e|ed|ing)|record(?:ed|ing)?|film(?:ed|ing)?|publish(?:ed|ing)?|advertis(?:e|ed|ing)|convert(?:ed|ing)?|renovat(?:e|ed|ing)|refurbish(?:ed|ing)?|upgrad(?:e|ed|ing)|repair(?:ed|ing)?|redesign(?:ed|ing)?|relocat(?:e|ed|ing)|equip(?:ped|ping)?|paint(?:ed|ing)?|remov(?:e|ed|ing)|overhaul(?:ed|ing)?|partition(?:ed|ing)?|stag(?:e|ed|ing)|recruit(?:ed|ing)?|reserv(?:e|ed|ing)|allocat(?:e|ed|ing)|dedicat(?:e|ed|ing)|fund(?:ed|ing)?|subsidi[sz](?:e|ed|ing)|sponsor(?:ed|ing)?|post(?:ed|ing)?|sell(?:ing)?|count(?:ed|ing)?|measur(?:e|ed|ing)|surve(?:y|yed|ying)|hand\\s+out|distribut(?:e|ed|ing)|print(?:ed|ing)?|translat(?:e|ed|ing)|rotat(?:e|ed|ing)|pilot(?:ed|ing)?|trial(?:led|ling)?|test(?:ed|ing)?|monitor(?:ed|ing)?|review(?:ed|ing)?|assign(?:ed|ing)?|pair(?:ed|ing)?|match(?:ed|ing)?|link(?:ed|ing)?|connect(?:ed|ing)?|contact(?:ed|ing)?|approach(?:ed|ing)?|negotiat(?:e|ed|ing)|partner(?:ed|ing)?|rent(?:ed|ing)?|lease(?:d)?|borrow(?:ed|ing)?|share(?:d)?|shar(?:ing)|bring(?:ing)?\\s+in|set(?:ting)?\\s+aside|turn(?:ed|ing)?\\s+(?:into|the)|cut(?:ting)?|raise|lower|double|halve|shorten(?:ed|ing)?|lengthen(?:ed|ing)?|widen(?:ed|ing)?|simplif(?:y|ied|ying)|streamlin(?:e|ed|ing)|automat(?:e|ed|ing)|digiti[sz](?:e|ed|ing)|revamp(?:ed|ing)?|reorgani[sz](?:e|ed|ing)|restructur(?:e|ed|ing)|decorat(?:e|ed|ing)|brighten(?:ed|ing)?|light(?:ed|ing)?|furnish(?:ed|ing)?|carpet(?:ed|ing)?|plant(?:ed|ing)?|welcom(?:e|ed|ing)|greet(?:ed|ing)?|reward(?:ed|ing)?|celebrat(?:e|ed|ing)|advertis(?:e|ed|ing)|market(?:ed|ing)?|screen(?:ed|ing)?|broadcast(?:ing)?|stream(?:ed|ing)?|upload(?:ed|ing)?|updat(?:e|ed|ing)|redesign(?:ed|ing)?'
_ACTION_BASE = 'replace|install|create|introduce|set\\s+up|provide|offer|extend|hold|run|organi[sz]e|open|hire|launch|build|buy|put|move|convert|host|appoint|recruit|reserve|allocate|fund|subsidi[sz]e|schedule|add|remove|paint|refurbish|renovate|upgrade|repair|redesign|relocate|equip|invite|arrange|start|establish|develop|design|include|promote|advertise|train|employ|reduce|increase|limit|ban|require|combine|split|divide|overhaul|make|give|use|turn|partition|stage|sponsor|sell|post|print|distribute|translate|rotate|pilot|trial|monitor|review|assign|pair|link|connect|contact|approach|negotiate|rent|lease|borrow|share|cut|raise|lower|double|halve|shorten|widen|simplify|streamline|automate|digiti[sz]e|revamp|reorgani[sz]e|restructure|decorate|brighten|furnish|plant|reward|celebrate|market|screen|broadcast|stream|upload|update|encourage|allow|ensure|keep|change|improve|expand|shift|bring|send|ask|invest|consider|dedicate|set\\s+aside|hand\\s+out|bring\\s+in|drop|scrap|restrict|relax|adopt|apply|register|record|film|produce|publish|serve|supply|stock|display|label|signpost'
_ENUM = '(?:(?:first|firstly|second|secondly|third|thirdly|fourth|finally|lastly|next|also|moreover|furthermore|additionally|in\\s+addition|to\\s+begin\\s+with|to\\s+start\\s+with|above\\s+all|most\\s+importantly|equally|besides|then|as\\s+a\\s+first\\s+step|as\\s+a\\s+second\\s+step|on\\s+top\\s+of\\s+(?:this|that))\\s*,?\\s+)?'
_PROPOSAL_NOUNS = 'suggestion|recommendation|proposal|idea|solution|option|measure|step|way|improvement|change|plan|initiative|scheme|action|priority|move|strategy|approach|answer|remedy|fix|proposition|course\\s+of\\s+action'
_REC_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        'suggest_verb',
        "\\b(?:i|we)(?:\\s+|'m\\s+|\\s+am\\s+|\\s+are\\s+|'d\\s+)(?:would\\s+|strongly\\s+|firmly\\s+|also\\s+|therefore\\s+|thus\\s+)?(?:like\\s+to\\s+)?(?:gonna\\s+|going\\s+to\\s+)?(?:suggest|recommend|propose|advise|urge|encourage|call\\s+for|put\\s+forward)\\b",
    ),
    (
        'wish_verb',
        '\\b(?:i|we)\\s+(?:would\\s+)?(?:like|want|wish)\\s+to\\s+(?:see|ask\\s+for|request|have)\\b',
    ),
    (
        'proposal_states',
        '\\b(?:this|the|my|our)\\s+(?:proposal|report|document|paper)\\s+(?:recommends|suggests|proposes|outlines|puts\\s+forward|sets\\s+out|calls\\s+for|presents|makes)\\b',
    ),
    (
        'writing_to_propose',
        '\\b(?:writing|write|would\\s+like)\\s+to\\s+(?:propose|suggest|recommend|put\\s+forward|outline|set\\s+out)\\b',
    ),
    (
        'suggestion_noun',
        '\\b(?:(?:my|our|the|a|another|one|first|second|third|final|main|other|best|simplest|easiest|most\\s+effective|next|last|key|central|obvious|immediate|long-term|short-term)\\s+)?(?:first\\s+|second\\s+|third\\s+|final\\s+|main\\s+|other\\s+|next\\s+|key\\s+|big\\s+|small\\s+)?(?:'
        + _PROPOSAL_NOUNS
        + ')s?\\s+(?:is|would\\s+be|could\\s+be|might\\s+be|are|involves|consists\\s+of|concerns)\\s+(?:to\\b|that\\b|a\\b|an\\b|the\\b|for\\b|as\\s+follows|simple\\s*:|clear\\s*:|two|three|four|\\w+ing\\b)',
    ),
    (
        'it_would_be',
        '\\b(?:i\\s+(?:think|believe|feel)\\s+(?:that\\s+)?)?it\\s+(?:would|could|might)\\s+(?:also\\s+)?be\\s+(?:advisable|worth|worthwhile|a\\s+good\\s+idea|beneficial|sensible|wise|useful|helpful|possible|better|interesting|ideal|appropriate|preferable|desirable|worth\\s+considering)\\b',
    ),
    (
        'it_is_essential',
        "\\b(?:it\\s+is|it's)\\s+(?:essential|necessary|vital|crucial|advisable|important|imperative|high\\s+time)\\s+(?:to|that|for)\\b",
    ),
    (
        'should',
        '\\b(?:should|ought\\s+to|must)\\s+(?:be\\s+|also\\s+|therefore\\s+|then\\s+|definitely\\s+|certainly\\s+|ideally\\s+)?(?!not\\b)[a-z]+',
    ),
    (
        'need_to',
        '\\b(?:we|i|you|the\\s+(?:council|college|school|library|centre|center|company|club|committee|management|staff|organi[sz]ers|team|department|university|town|city|board|canteen|kitchen|office|manager|principal|director|owners?))\\s+(?:also\\s+|really\\s+|urgently\\s+)?needs?\\s+to\\s+(?!be\\s+(?:able|careful))[a-z]+',
    ),
    (
        'could',
        '\\b(?:could|might)\\s+(?:be\\s+|also\\s+|even\\s+|easily\\s+|then\\s+)?(?:'
        + _ACTION_VERBS
        + ')\\b',
    ),
    (
        'we_can',
        '\\b(?:we|i|you|the\\s+(?:council|college|school|library|centre|center|company|club|committee|management|staff|organi[sz]ers|team|department|university|town|city|board|canteen|kitchen|office|manager|principal|director|owners?|union))\\s+can\\s+(?:also\\s+|easily\\s+|then\\s+|simply\\s+|even\\s+)?(?:'
        + _ACTION_VERBS
        + '|do|count|compare|ask|use|invite|sell|post|put|make|give|run|hold|create|set|keep|start|try|hire|bring|choose|pick|book|contact|talk|write|call|check|measure|track|collect|gather|reward|thank)\\b',
    ),
    ('why_not', '\\bwhy\\s+not\\b'),
    (
        'imperative',
        '^(?:[-•*·]\\s*|\\d+[.)]\\s*|[*_]+)?'
        + _ENUM
        + '(?:[*_]+)?(?:'
        + _ACTION_BASE
        + ')\\s+(?:a|an|the|some|more|new|all|every|each|our|its|their|this|these|those|two|three|four|five|at\\s+least|\\w+ing|\\w+s\\b|[A-Z]\\w+)',
    ),
    (
        'gerund_start',
        '^(?:[*_]+)?(?:'
        + _ACTION_VERBS
        + ')\\b.*\\b(?:would|will|could|might|is\\s+(?:a\\s+good\\s+idea|advisable|necessary|essential|worth|the\\s+obvious))\\b',
    ),
    (
        'declarative_future',
        '^(?![*_]*(?:this|these|that|those|it|such|they|there|as\\s+a\\s+result|in\\s+this\\s+way|the\\s+(?:result|effect|benefit|advantage|outcome)s?)\\b)(?:[A-Za-z][^.;:!?]{0,70}?\\s)?(?:would|will|could)\\s+(?:also\\s+|then\\s+|therefore\\s+|initially\\s+|ideally\\s+)?(?:be\\s+)?(?:'
        + _ACTION_VERBS
        + '|take\\s+the\\s+form|happen|meet|feature|serve|welcome|house|store|display|remain|stay|offer|charge|cost|last|begin|form|become|let|see|comprise|consist|operate|open|close|run|take\\s+place)\\b',
    ),
    (
        'imperative_heading',
        '^(?:recommendation|suggestion|proposal)\\s*(?:\\d+|one|two|three|[a-c])?\\s*:',
    ),
)
_REC_RES = tuple(((name, re.compile(p, re.I)) for name, p in _REC_PATTERNS))
_ANNOUNCEMENT = re.compile(
    '\\b(?:purpose|aim|goal|objective)\\s+of\\s+(?:this|the|my|our)\\s+(?:proposal|report|document)\\b|\\b(?:this|the|my|our)\\s+(?:proposal|report|document)\\s+(?:recommends|suggests|proposes|outlines|puts\\s+forward|sets\\s+out|presents|makes)\\b|\\b(?:propose|suggest|recommend|put\\s+forward|outline)\\s+(?:the\\s+following|three|two|four|several|a\\s+number\\s+of|some|a\\s+few|a\\s+series\\s+of|a\\s+three-part|a\\s+two-part)\\b|\\b(?:writing|write)\\s+(?:this\\s+proposal\\s+)?to\\s+(?:propose|suggest|recommend|put\\s+forward|outline)\\s+(?:some|two|three|four|several|a\\s+few|a\\s+number\\s+of|the\\s+following|how|ways|improvements|changes|ideas|measures)\\b',
    re.I,
)
_PRONOUN_MODAL = re.compile(
    '\\b(?:this|these|that|those|it|such\\s+\\w+|they|there|which)\\s+(?:would|will|could|can|might)\\b',
    re.I,
)
_CLOSING_APPEAL = re.compile(
    '\\b(?:urge|hope|hoping|grateful|consider(?:ing)?|adopt|approve|approval|agree|support\\s+this|look\\s+forward|in\\s+conclusion|to\\s+sum\\s+up|to\\s+conclude|overall|all\\s+in\\s+all|thank\\s+you)\\b',
    re.I,
)
_BENEFIT_HEADING = re.compile(
    'benefit|advantage|effect|outcome|impact|result|why\\s+(?:this|it|the)|gain', re.I
)
_REC_HEADING = re.compile(
    'recommend|suggest|propos|action|plan|measure|change|solution|idea|what\\s+(?:should|could|we)|how\\s+(?:to|the|we)|step',
    re.I,
)
_ENUM_START = re.compile(
    '^(?:[*_]+)?(?:first|firstly|second|secondly|third|thirdly|fourth|finally|lastly|next|also|moreover|furthermore|additionally|in\\s+addition|to\\s+begin\\s+with|to\\s+start\\s+with|equally|besides)\\b',
    re.I,
)
_ELABORATION_START = re.compile(
    '^(?:this|these|that|those|it|such|the\\s+(?:same|latter|former)|they)\\b', re.I
)
_CAUSAL_RES = tuple(
    (
        re.compile(p, re.I)
        for p in (
            '\\bbecause\\b',
            '\\bsince\\b',
            '\\bgiven\\s+that\\b',
            '\\bdue\\s+to\\b',
            '\\bowing\\s+to\\b',
            '\\bthe\\s+(?:main\\s+|first\\s+|second\\s+)?reasons?\\b',
            '\\bfor\\s+(?:this|that|two|three|several|the\\s+following)\\s+reasons?\\b',
            '\\bthis\\s+is\\s+because\\b',
            '\\b(?:this|that|which)\\s+is\\s+why\\b',
            '\\bthat\\s+is\\s+the\\s+reason\\b',
            '\\bas\\s+(?:i|we|you|they|it|there|this|these|those|the|our|my|most|many|few|some|students|people|staff|residents|users|members|families|visitors|customers|employees|nobody|no\\s+one)\\b',
            '\\btherefore\\b',
            '\\bthus\\b',
            '\\bhence\\b',
            '\\bconsequently\\b',
            '\\bso\\s+(?:i|we)\\s+(?:suggest|recommend|propose|think|believe)\\b',
            '\\bin\\s+(?:the\\s+)?light\\s+of\\b',
            '\\bconsidering\\s+(?:that|the|how)\\b',
            '\\bgiven\\s+the\\b',
            '\\bthanks\\s+to\\b',
        )
    )
)
_PROBLEM_RES = tuple(
    (
        re.compile(p, re.I)
        for p in (
            '\\bproblems?\\b',
            '\\bissues?\\b',
            '\\bdifficult(?:y|ies)?\\b',
            '\\black(?:s|ing)?\\b',
            '\\binsufficient\\b',
            '\\bshortage\\b',
            '\\bpoor(?:ly)?\\b',
            '\\bunwelcoming\\b',
            '\\buncomfortable\\b',
            '\\bunder-?used\\b',
            '\\brarely\\b',
            '\\bseldom\\b',
            '\\bhardly\\s+(?:ever|any)\\b',
            '\\b(?:has|have)\\s+(?:fallen|dropped|declined|decreased|halved|shrunk)\\b',
            '\\bdeclin(?:e|ed|ing)\\b',
            '\\bdrop(?:ped)?\\s+(?:in|of)\\b',
            '\\blow\\s+(?:attendance|numbers|turnout|uptake|participation)\\b',
            '\\bnot\\s+enough\\b',
            '\\bno\\s+longer\\b',
            '\\btoo\\s+(?:few|little|crowded|dark|noisy|far|late|early|small|old|slow|expensive|complicated|cold|hot|busy|long|short)\\b',
            '\\bcurrently\\b',
            '\\bat\\s+present\\b',
            '\\bat\\s+the\\s+moment\\b',
            '\\bnowadays\\b',
            '\\bunfortunately\\b',
            '\\bhowever\\b',
            '\\bcomplain(?:ts?|ed|ing)?\\b',
            '\\bfrustrat(?:ed|ing|ion)\\b',
            '\\bconfus(?:ed|ing|ion)\\b',
            '\\bstruggl(?:e|es|ing)\\b',
            '\\bfail(?:s|ed|ing|ure)?\\s+to\\b',
            '\\bunable\\s+to\\b',
            '\\bcannot\\b',
            "\\bcan(?:')?t\\b",
            '\\bdo(?:es)?\\s+not\\s+(?:work|attract|appeal|know|use|offer|have|allow|provide|feel)\\b',
            "\\bdon'?t\\s+(?:work|attract|appeal|know|use|offer|have|allow|provide|feel)\\b",
            '\\bout\\s*dated\\b',
            '\\bold-?fashioned\\b',
            '\\bnobody\\b',
            '\\bno\\s+one\\b',
            '\\bwaste\\b',
            '\\bdamag(?:e|ed|ing)\\b',
            '\\bput(?:s|ting)?\\s+(?:\\w+\\s+){0,3}off\\b',
            '\\bstay\\s+away\\b',
            '\\bkeep\\s+away\\b',
            '\\bnot\\s+(?:very\\s+)?(?:popular|attractive|welcoming|easy|clear|convenient)\\b',
            '\\bnowhere\\b',
            '\\b(?:has|have|there\\s+is|there\\s+are)\\s+no\\b',
            '\\b(?:almost\\s+|nearly\\s+|often\\s+|usually\\s+)?empty\\b',
            '\\bclos(?:es|ed|ing)\\s+(?:at|too\\s+early|early|before)\\b',
            '\\b(?:broken|faulty|out\\s+of\\s+order|worn|threadbare|ageing|aging|dated|dull|grim|lifeless|neglect(?:ed)?|derelict)\\b',
        )
    )
)
_EFFECT_RES = tuple(
    (
        re.compile(p, re.I)
        for p in (
            '\\b(?:would|will|could|might|may|can)\\s+(?:also\\s+|certainly\\s+|probably\\s+|definitely\\s+|undoubtedly\\s+|then\\s+|not\\s+only\\s+|therefore\\s+|thus\\s+|surely\\s+|easily\\s+|quickly\\s+|greatly\\s+|significantly\\s+)?(?:lead\\s+to|result\\s+in|mean|help|encourage|attract|increase|reduce|improve|boost|enable|allow|ensure|bring|create|give|provide|save|cut|raise|lower|prevent|turn|benefit|motivate|persuade|convince|draw|keep|stop|solve|address|tackle|contribute|generate|promote|strengthen|support|foster|enhance|revive|restore|double|halve|widen|broaden|open\\s+up|free\\s+up|speed\\s+up|cheer\\s+up|liven\\s+up|become|make|appeal|feel|see|get|find|have|be\\s+(?:able|more|less|easier|better|safer|cheaper|quicker|happier|healthier|likely|bound|sure|encouraged|attracted|motivated|tempted|willing|keen|reluctant|reduced|improved|solved|met|informed|aware|welcome))\\b',
            '\\bso\\s+that\\b',
            '\\bin\\s+order\\s+(?:to|that)\\b',
            '\\bto\\s+(?:ensure|make\\s+sure|help|allow|enable|encourage|attract|reduce|prevent|increase|improve|give|keep|avoid|boost|motivate|persuade|draw|bring|create|save|cut|raise|lower|solve|tackle|address|promote|strengthen|support|foster|enhance|revive|restore|meet|satisfy|benefit)\\b',
            '\\bas\\s+a\\s+result\\b',
            '\\bconsequently\\b',
            '\\btherefore\\b',
            '\\bthus\\b',
            '\\b(?:in\\s+)?this\\s+way\\b',
            '\\bthereby\\b',
            '\\bhence\\b',
            '\\bthe\\s+(?:main\\s+|great\\s+|obvious\\s+|clear\\s+)?(?:result|effect|outcome|benefit|impact|advantage|consequence|gain)s?\\s+(?:of\\s+[^.;,]{1,50}?\\s+)?(?:would|will|is|are|being)\\b',
            '\\bleading\\s+to\\b',
            '\\bresulting\\s+in\\b',
            '\\b(?:is|are)\\s+(?:likely|bound|sure|certain)\\s+to\\b',
            '\\bwhich\\s+(?:would|will|could|might|in\\s+turn)\\b',
            '\\bnot\\s+only\\s+(?:would|will|could)\\b',
            '\\bi\\s+(?:expect|believe|am\\s+confident|am\\s+sure|anticipate|predict|am\\s+convinced)\\s+(?:that\\s+)?(?:this|these|it|they|the|such|more|fewer)\\b',
            '\\b(?:this|these|it|they|such\\s+\\w+)\\s+(?:would|will|could|might)\\s+(?:be|become|no\\s+longer|soon|certainly|surely|then)\\b',
            '\\bmore\\s+(?:\\w+\\s+){0,2}(?:would|will|could|might)\\b',
            '\\bfewer\\s+(?:\\w+\\s+){0,2}(?:would|will|could|might)\\b',
            '\\bbenefit(?:s|ed)?\\s+(?:greatly|from|enormously|hugely)\\b',
            '\\b(?:if|once)\\s+(?:this|these|it|they|such|the)\\b.*\\b(?:would|will|could)\\b',
            '\\b(?:this|it|that|which|such\\s+a\\s+\\w+)\\s+(?:means|offers|gives|brings|provides|creates|allows|lets|makes|saves|frees|removes|reduces|increases|boosts|improves|encourages|attracts|ensures|guarantees|helps|enables|opens|restores|revives|builds|strengthens)\\b',
            '\\b(?:would|will|could|can)\\s+(?:repay|reward|pay\\s+off|transform|revitali[sz]e|regenerate|breathe\\s+new\\s+life|go\\s+a\\s+long\\s+way|tackle|address|remove|eliminate|ease|relieve|lift|cut|spread|reach|serve|appeal|win|convince|reassure|tempt|entice|draw\\s+in|bring\\s+in|pull\\s+in)\\b',
            '\\bfor\\s+(?:residents|students|staff|users|members|families|visitors|customers|employees|teachers|parents|local\\s+\\w+|the\\s+\\w+),\\s+(?:this|it|the\\s+\\w+|such\\s+\\w+)\\s+(?:means|offers|gives|would|will|could|brings|provides)\\b',
            '\\b(?:reduc|boost|improv|increas|strengthen|encourag|foster|promot|lower|rais|widen|deepen|sharpen|build|restor|reviv)(?:es|ing)\\b\\s',
            '\\bcan\\s+only\\s+(?:help|benefit|improve|strengthen)\\b',
            '\\b(?:the|a)\\s+(?:chance|opportunity|way|means|platform|space|reason)\\s+to\\b',
            '\\bgiving\\s+(?:each|every|them|students|residents|users|staff|members|people|everyone|\\w+)\\s+(?:a|an|the|more|less|time|space|chance)\\b',
            '\\bwould\\s+(?:no\\s+longer|never\\s+again|soon|finally|at\\s+last)\\b',
            '\\bmany\\s+times\\s+over\\b',
            '\\bpay(?:s|ing)?\\s+for\\s+itself\\b',
            '\\b(?:instantly|immediately|thereby|thus|effectively|ultimately|in\\s+turn)\\s+\\w+ing\\b',
            ',\\s*(?:doubling|halving|boosting|improving|increasing|reducing|cutting|saving|freeing|making|giving|creating|encouraging|attracting|allowing|enabling|helping|ensuring|preventing|removing|easing|relieving|bringing|turning|opening|restoring|reviving|building|fostering|strengthening|widening|raising|lowering|keeping|leaving|sparing)\\s+(?:the|a|an|our|their|its|his|her|more|less|fewer|every|each|students|people|residents|users|staff|members|visitors|customers|families|everyone|us|them|it)\\b',
        )
    )
)
_PAST_RES = re.compile(
    '\\b(?:was|were|had|did|used\\s+to|last\\s+(?:year|term|month|time)|previously|in\\s+the\\s+past|ago|back\\s+then)\\b',
    re.I,
)
_MODAL_RES = re.compile('\\b(?:would|will|could|should|might|shall|can)\\b|\\bgoing\\s+to\\b', re.I)
_CONTRACTION_RES = re.compile(
    "\\b(?:it's|that's|there's|what's|he's|she's|let's|here's|who's|\\w+n't|\\w+'re|\\w+'ve|\\w+'ll|\\w+'d|i'm)\\b",
    re.I,
)
_SECOND_PERSON_RES = re.compile('\\b(?:you|your|yours|yourself)\\b', re.I)
_DEAR_RES = re.compile('^\\s*dear\\b', re.I)
_SIGNOFF_RES = re.compile(
    '\\b(?:yours\\s+(?:sincerely|faithfully)|kind\\s+regards|best\\s+regards|regards)\\b', re.I
)
_READER_FROM_TASK_RES = tuple(
    (
        re.compile(p, re.I)
        for p in (
            "\\breader(?:\\s+of\\s+your\\s+proposal)?\\s+is\\s+(?:the\\s+|your\\s+)?([a-z][a-z'\\- ]{2,40}?)(?:,|\\.|\\s+who\\b|\\s+which\\b|$)",
            "\\bproposal\\s+for\\s+(?:the\\s+|your\\s+)?([a-z][a-z'\\- ]{2,40}?)(?:,|\\.|$)",
            "\\baddress\\s+(?:the\\s+|your\\s+)?([a-z][a-z'\\- ]{2,40}?)\\s+as\\s+the\\s+reader\\b",
        )
    )
)
_STOP_READER = {'the', 'your', 'a', 'an', 'of', 'for', 'to', 'and', 'who', 'which'}


def _norm_reader_terms(phrases: list[str]) -> list[str]:
    terms: list[str] = []
    for ph in phrases:
        ph = re.sub('\\s+', ' ', ph.strip().lower())
        if not ph:
            continue
        if ph not in terms:
            terms.append(ph)
        words = [w for w in ph.replace("'s", '').split() if w not in _STOP_READER]
        if words:
            head = words[0] if ' of ' in ph else words[-1]
            if head not in terms and len(head) > 2:
                terms.append(head)
    return terms


def reader_terms_from_task(task_text: str) -> list[str]:
    """Extract reader names from English task wording."""
    found: list[str] = []
    for rx in _READER_FROM_TASK_RES:
        for m in rx.finditer(task_text or ''):
            found.append(m.group(1))
    return _norm_reader_terms(found)


def _first_match(rxs, text: str, *, after: int = 0) -> tuple[re.Match | None, str]:
    best: re.Match | None = None
    for rx in rxs:
        for m in rx.finditer(text):
            if m.start() < after:
                continue
            if best is None or m.start() < best.start():
                best = m
            break
    return (best, best.group(0) if best else '')


def _mask(text: str, span: Span, base: int) -> str:
    """Mask the trigger with spaces to avoid treating the action itself as its reason or effect."""
    s, e = (span.start - base, span.end - base)
    return text[:s] + ' ' * (e - s) + text[e:]


def x_is_transition(sent: Sentence) -> bool:
    """Treat a short sentence without problem or causal markers as a transition."""
    if len(sent.text.split()) > 12:
        return False
    return not any((rx.search(sent.text) for rx in _PROBLEM_RES + _CAUSAL_RES))


def _stem(word: str) -> str:
    w = word.lower()
    for suf in ('ing', 'ed', 'es', 's'):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def _head_verb(sent_text: str, trigger: str, m_text: str) -> str:
    """Find an action stem for merging an imperative and its repeated elaboration."""
    words = re.findall('[a-z]+', m_text.lower())
    for w in words:
        if w in (
            'first',
            'firstly',
            'second',
            'secondly',
            'third',
            'thirdly',
            'finally',
            'lastly',
            'next',
            'also',
            'moreover',
            'furthermore',
            'additionally',
            'in',
            'addition',
            'to',
            'begin',
            'with',
            'start',
            'should',
            'could',
            'might',
            'would',
            'will',
            'be',
            'we',
            'i',
            'you',
            'the',
            'also',
            'then',
            'can',
            'need',
            'needs',
            'must',
            'ought',
            'it',
            'is',
            'a',
            'an',
            'suggest',
            'recommend',
            'propose',
            'advise',
            'urge',
            'like',
            'am',
            'going',
            'gonna',
            'writing',
            'write',
            'that',
            'this',
            'my',
            'our',
            'one',
            'another',
            'best',
        ):
            continue
        return _stem(w)
    return ''


def _block_heading_for(
    sentence: Sentence, sentences: list[Sentence], headings: list[Heading]
) -> Heading | None:
    """Find the closest heading above the first sentence of the paragraph."""
    first = next((x for x in sentences if x.para == sentence.para), sentence)
    above = [h for h in headings if h.span.end <= first.span.start]
    return above[-1] if above else None


_ANNOUNCEMENTS_SINK: list[Sentence] = []


def _detect_recommendations(
    text: str, sentences: list[Sentence], headings: list[Heading] | None = None
) -> list[Recommendation]:
    headings = headings or []
    last_para = max((x.para for x in sentences), default=0)
    recs: list[Recommendation] = []
    announcements: list[Sentence] = _ANNOUNCEMENTS_SINK
    prev_was_rec = False
    for s in sentences:
        trigger = ''
        tspan: Span | None = None
        mtext = ''
        heading = _block_heading_for(s, sentences, headings)
        under_benefit = bool(heading and _BENEFIT_HEADING.search(heading.text))
        under_rec = bool(heading and _REC_HEADING.search(heading.text))
        for name, rx in _REC_RES:
            m = rx.search(s.text)
            if not m:
                continue
            if name == 'declarative_future':
                if under_benefit or _PRONOUN_MODAL.search(s.text[: m.end()]):
                    continue
            trigger, mtext = (name, m.group(0))
            tspan = _remap(s, m.start(), m.end(), text)
            break
        if (
            not trigger
            and under_rec
            and _ENUM_START.match(s.text)
            and re.search('\\b(?:would|will|could|should|can|is|are)\\b', s.text, re.I)
        ):
            trigger, mtext = ('enumerated_under_heading', s.text[:30])
            tspan = s.span
        if not trigger:
            prev_was_rec = False
            continue
        if trigger in (
            'suggest_verb',
            'proposal_states',
            'writing_to_propose',
            'suggestion_noun',
        ) and _ANNOUNCEMENT.search(s.text):
            announcements.append(s)
            prev_was_rec = False
            continue
        if (
            s.para == last_para
            and last_para > 0
            and _CLOSING_APPEAL.search(s.text)
            and (
                trigger
                in (
                    'suggest_verb',
                    'should',
                    'declarative_future',
                    'it_would_be',
                    'we_can',
                    'need_to',
                )
            )
        ):
            prev_was_rec = False
            continue
        if (
            prev_was_rec
            and recs
            and (recs[-1].sentence.para == s.para)
            and _ELABORATION_START.match(s.text)
            and (trigger in ('should', 'could', 'declarative_future'))
        ):
            continue
        if recs and recs[-1].sentence.para == s.para and (recs[-1].sentence.index == s.index - 1):
            hv_prev = _head_verb(
                recs[-1].sentence.text,
                recs[-1].trigger,
                text[recs[-1].trigger_span.start : recs[-1].trigger_span.end],
            )
            hv_now = _head_verb(s.text, trigger, mtext)
            if hv_prev and hv_now and (hv_prev == hv_now) and (recs[-1].trigger == 'imperative'):
                continue
        recs.append(
            Recommendation(len(recs), s, Span(s.span.start, s.span.end), trigger, tspan or s.span)
        )
        prev_was_rec = True
    by_index = {s.index: s for s in sentences}
    rec_sent_idx = {r.sentence.index for r in recs}
    para_of: dict[int, list[Sentence]] = {}
    sect_of: dict[int, list[Sentence]] = {}
    for x in sentences:
        para_of.setdefault(x.para, []).append(x)
        sect_of.setdefault(x.section, []).append(x)

    def _sect_text(p: int) -> str:
        xs = sect_of.get(p) or []
        return text[xs[0].span.start : xs[-1].span.end] if xs else ''

    def _is_problem_block(p: int) -> bool:
        t = _sect_text(p)
        return sum((1 for rx in _PROBLEM_RES if rx.search(t))) >= 2

    def _is_benefit_block(p: int) -> bool:
        xs = sect_of.get(p) or []
        if not xs:
            return False
        h = _block_heading_for(xs[0], sentences, headings)
        if h and _BENEFIT_HEADING.search(h.text):
            return True
        t = _sect_text(p)
        return sum((1 for rx in _EFFECT_RES if rx.search(t))) >= 2

    for k, r in enumerate(recs):
        end = r.sentence.span.end
        nxt_rec_idx = recs[k + 1].sentence.index if k + 1 < len(recs) else None
        j = r.sentence.index + 1
        while (
            j in by_index
            and by_index[j].para == r.sentence.para
            and (nxt_rec_idx is None or j < nxt_rec_idx)
            and (j <= r.sentence.index + 3)
        ):
            end = by_index[j].span.end
            j += 1
        r.unit = Span(r.sentence.span.start, end)
        unit_text = _mask(text[r.unit.start : r.unit.end], r.trigger_span, r.unit.start)
        sect_sents = sect_of.get(r.sentence.section) or []
        pos = next((i for i, x in enumerate(sect_sents) if x.index == r.sentence.index), 0)
        before = [x for x in sect_sents[max(0, pos - 2) : pos] if x.index not in rec_sent_idx]
        windows: list[tuple[int, str, str]] = [(r.unit.start, unit_text, 'unit')]
        if before:
            windows.append(
                (before[0].span.start, text[before[0].span.start : before[-1].span.end], 'before')
            )
        if pos == 0 and r.sentence.section > 0:
            pb = (sect_of.get(r.sentence.section - 1) or [])[-2:]
            if pb:
                windows.append(
                    (pb[0].span.start, text[pb[0].span.start : pb[-1].span.end], 'prev_block')
                )
        for base, seg, _where in windows:
            m, marker = _first_match(_CAUSAL_RES + _PROBLEM_RES, seg)
            if m:
                r.reason = Span(base + m.start(), base + m.end())
                r.reason_marker = marker
                break
        if r.reason is None:
            p = r.sentence.section - 1
            hops = 0
            ann_idx = {x.index for x in _ANNOUNCEMENTS_SINK}
            while p >= 0 and hops < 3:
                xs = sect_of.get(p) or []
                if (
                    xs
                    and (not all((x.index in ann_idx for x in xs)))
                    and (not (len(xs) == 1 and x_is_transition(xs[0])))
                ):
                    break
                p -= 1
                if xs:
                    hops += 1
            if (
                p >= 0
                and _is_problem_block(p)
                and (not any((x.index in rec_sent_idx for x in sect_of[p])))
            ):
                xs = sect_of[p]
                seg = text[xs[0].span.start : xs[-1].span.end]
                m, marker = _first_match(_PROBLEM_RES, seg)
                if m:
                    r.reason = Span(xs[0].span.start + m.start(), xs[0].span.start + m.end())
                    r.reason_marker = marker + ' [problem block]'
        m3, marker3 = _first_match(_EFFECT_RES, unit_text)
        if m3:
            r.effect = Span(r.unit.start + m3.start(), r.unit.start + m3.end())
            r.effect_marker = marker3
        else:
            p = r.sentence.section + 1
            if (
                p in sect_of
                and _is_benefit_block(p)
                and (not any((x.index in rec_sent_idx for x in sect_of[p])))
            ):
                xs = sect_of[p]
                seg = text[xs[0].span.start : xs[-1].span.end]
                m4, marker4 = _first_match(_EFFECT_RES, seg)
                if m4:
                    r.effect = Span(xs[0].span.start + m4.start(), xs[0].span.start + m4.end())
                    r.effect_marker = marker4 + ' [benefit block]'
    return recs


def _remap(s: Sentence, a: int, b: int, text: str) -> Span:
    """Map offsets in whitespace-folded text back to original character positions."""
    raw = text[s.span.start : s.span.end]
    folded_to_raw: list[int] = []
    prev_space = False
    for i, ch in enumerate(raw):
        if ch.isspace():
            if prev_space:
                continue
            prev_space = True
        else:
            prev_space = False
        folded_to_raw.append(i)
    lead = len(raw) - len(raw.lstrip())
    folded_to_raw = [i for i in folded_to_raw if i >= lead]
    if not folded_to_raw:
        return s.span
    a = min(max(a, 0), len(folded_to_raw) - 1)
    b = min(max(b, 1), len(folded_to_raw))
    return Span(s.span.start + folded_to_raw[a], s.span.start + folded_to_raw[b - 1] + 1)


_TASK_POINT_KINDS: tuple[tuple[str, re.Pattern], ...] = (
    ('reader', re.compile('\\b(?:address|as\\s+the\\s+reader|reader)\\b', re.I)),
    ('reason', re.compile('\\breason', re.I)),
    ('effect', re.compile('\\b(?:effect|change|result|impact|outcome|benefit)', re.I)),
    ('recommendations', re.compile('\\b(?:recommend|feature|measure|suggest|propos)', re.I)),
    (
        'problem',
        re.compile(
            '\\b(?:problem|difficult|wrong|issue|identify|explain\\s+why|unwelcoming)', re.I
        ),
    ),
)
_MIN_N_RES = re.compile('\\b(?:at\\s+least\\s+)?(one|two|three|four|\\d)\\b', re.I)
_NUM = {'one': 1, 'two': 2, 'three': 3, 'four': 4}


def classify_task_point(point: str) -> tuple[str, int]:
    """Classify a task point and find its minimum recommendation count when supplied."""
    for kind, rx in _TASK_POINT_KINDS:
        if rx.search(point):
            n = 1
            if kind == 'recommendations':
                m = _MIN_N_RES.search(point)
                if m:
                    g = m.group(1).lower()
                    n = _NUM.get(g) or (int(g) if g.isdigit() else 1)
            return (kind, n)
    return ('unknown', 0)


def analyse_proposal(
    text: str,
    *,
    task_text: str = '',
    task_points: list[str] | None = None,
    min_recommendations: int = 2,
    word_range: tuple[int, int] | None = None,
    reader_terms: list[str] | None = None,
) -> ProposalAnalysis:
    """Locate proposal signals using English rules and optional task constraints.
    Call sequentially: the recommendation detector uses a shared announcement list."""
    text = text or ''
    headings, sentences = segment(text)
    words = [w for w in re.split('\\s+', text.strip()) if w]
    word_count = len(words)
    _ANNOUNCEMENTS_SINK.clear()
    recs = _detect_recommendations(text, sentences, headings)
    announcements = list(_ANNOUNCEMENTS_SINK)
    terms = list(reader_terms) if reader_terms else reader_terms_from_task(task_text)
    findings: list[Finding] = []
    n = len(recs)
    findings.append(
        Finding(
            RULE_RECOMMENDATION_COUNT,
            'ok' if n >= min_recommendations else 'gap',
            SEVERITY[RULE_RECOMMENDATION_COUNT],
            recs[0].sentence.span if recs else None,
            recs[0].sentence.text if recs else '',
            f'{n} recommendation unit(s) located; minimum {min_recommendations}',
            {'count': n, 'min': min_recommendations, 'triggers': [r.trigger for r in recs]},
        )
    )
    missing_reason = [r for r in recs if not r.has_reason]
    missing_effect = [r for r in recs if not r.has_effect]

    def _marker_sentence(span: Span | None) -> tuple[Span | None, str]:
        """Return the whole sentence containing a matched marker as evidence."""
        if span is None:
            return (None, '')
        for x in sentences:
            if x.span.start <= span.start < x.span.end:
                return (x.span, x.text)
        return (span, text[span.start : span.end])

    ok_reason = _marker_sentence(recs[0].reason if recs and (not missing_reason) else None)
    ok_effect = _marker_sentence(recs[0].effect if recs and (not missing_effect) else None)
    findings.append(
        Finding(
            RULE_RECOMMENDATION_REASON,
            'gap' if missing_reason else 'ok' if recs else 'info',
            SEVERITY[RULE_RECOMMENDATION_REASON],
            missing_reason[0].sentence.span if missing_reason else ok_reason[0],
            missing_reason[0].sentence.text if missing_reason else ok_reason[1],
            (
                f'{len(missing_reason)} of {n} recommendation(s) have no reason nearby'
                if recs
                else 'no recommendation located, reason check not applicable'
            ),
            {
                'missing': [r.index for r in missing_reason],
                'markers': [r.reason_marker for r in recs],
            },
        )
    )
    findings.append(
        Finding(
            RULE_RECOMMENDATION_EFFECT,
            'gap' if missing_effect else 'ok' if recs else 'info',
            SEVERITY[RULE_RECOMMENDATION_EFFECT],
            missing_effect[0].sentence.span if missing_effect else ok_effect[0],
            missing_effect[0].sentence.text if missing_effect else ok_effect[1],
            (
                f'{len(missing_effect)} of {n} recommendation(s) state no expected effect'
                if recs
                else 'no recommendation located, effect check not applicable'
            ),
            {
                'missing': [r.index for r in missing_effect],
                'markers': [r.effect_marker for r in recs],
            },
        )
    )
    rec_spans = [r.unit for r in recs]
    problem_hit: Sentence | None = None
    marker_p = ''
    limit = max(1, len(sentences) * 2 // 3)
    for s in sentences[:limit]:
        if any((u.start <= s.span.start < u.end for u in rec_spans)):
            continue
        m, marker = _first_match(_PROBLEM_RES, s.text)
        if m:
            problem_hit, marker_p = (s, marker)
            break
    findings.append(
        Finding(
            RULE_PROBLEM_STATED,
            'ok' if problem_hit else 'gap',
            SEVERITY[RULE_PROBLEM_STATED],
            problem_hit.span if problem_hit else None,
            problem_hit.text if problem_hit else '',
            (
                'problem statement located before the recommendations'
                if problem_hit
                else 'no sentence naming a current problem was located before the recommendations'
            ),
            {'marker': marker_p},
        )
    )
    low = text.lower()
    named = [t for t in terms if t in low]
    you = len(_SECOND_PERSON_RES.findall(text))
    dear = bool(_DEAR_RES.match(text.lstrip()[:40]))
    to_line = any((h.text.lower().startswith('to:') for h in headings))
    if terms:
        status = 'ok' if named or (you >= 2 and (dear or to_line)) else 'gap'
    else:
        status = 'info'
    first_named_span = None
    if named:
        i = low.find(named[0])
        ls = text.rfind('\n', 0, i) + 1
        le = text.find('\n', i)
        le = len(text) if le < 0 else le
        first_named_span = Span(ls, le)
    findings.append(
        Finding(
            RULE_READER_ADDRESSED,
            status,
            SEVERITY[RULE_READER_ADDRESSED],
            first_named_span,
            text[first_named_span.start : first_named_span.end] if first_named_span else '',
            (
                f"reader named ({', '.join(named)})"
                if named
                else (
                    'reader not named; second person used %d time(s)' % you
                    if terms
                    else 'no reader term supplied by task'
                )
            ),
            {
                'terms': terms,
                'named': named,
                'second_person': you,
                'dear': dear,
                'to_line': to_line,
            },
        )
    )
    past = modal = 0
    for r in recs:
        u = text[r.unit.start : r.unit.end]
        past += len(_PAST_RES.findall(u))
        modal += len(_MODAL_RES.findall(u))
    findings.append(
        Finding(
            RULE_FUTURE_ORIENTATION,
            'gap' if recs and past > modal else 'info',
            SEVERITY[RULE_FUTURE_ORIENTATION],
            None,
            '',
            f'past markers {past} vs modal/future markers {modal} inside recommendation units',
            {'past': past, 'modal': modal},
        )
    )
    findings.append(
        Finding(
            RULE_HEADINGS_USED,
            'ok' if headings else 'info',
            SEVERITY[RULE_HEADINGS_USED],
            headings[0].span if headings else None,
            headings[0].text if headings else '',
            f'{len(headings)} heading(s)',
            {'headings': [h.text for h in headings]},
        )
    )
    cons = list(_CONTRACTION_RES.finditer(text))
    findings.append(
        Finding(
            RULE_CONTRACTIONS,
            'gap' if cons else 'info',
            SEVERITY[RULE_CONTRACTIONS],
            Span(cons[0].start(), cons[0].end()) if cons else None,
            cons[0].group(0) if cons else '',
            f'{len(cons)} contraction(s)',
            {'count': len(cons), 'forms': [c.group(0) for c in cons[:8]]},
        )
    )
    if word_range:
        lo, hi = word_range
        wr_status = (
            'ok'
            if lo <= word_count <= hi
            else 'gap' if word_count < lo * 0.9 or word_count > hi * 1.15 else 'info'
        )
        findings.append(
            Finding(
                RULE_WORD_RANGE,
                wr_status,
                SEVERITY[RULE_WORD_RANGE],
                None,
                '',
                f'{word_count} words; task range {lo}-{hi}',
                {'count': word_count, 'range': [lo, hi]},
            )
        )
    else:
        findings.append(
            Finding(
                RULE_WORD_RANGE,
                'info',
                SEVERITY[RULE_WORD_RANGE],
                None,
                '',
                f'{word_count} words; no range supplied',
                {'count': word_count},
            )
        )
    signoff = _SIGNOFF_RES.search(text)
    findings.append(
        Finding(
            RULE_LETTER_FRAME,
            'info',
            SEVERITY[RULE_LETTER_FRAME],
            Span(signoff.start(), signoff.end()) if signoff else None,
            signoff.group(0) if signoff else '',
            (
                'letter-style frame (Dear … / sign-off)'
                if dear or signoff
                else 'no letter-style frame'
            ),
            {'dear': dear, 'signoff': bool(signoff)},
        )
    )
    tp_results: list[TaskPointResult] = []
    by_rule = {f.rule_id: f for f in findings}
    for pt in task_points or []:
        kind, min_n = classify_task_point(pt)
        if kind == 'problem':
            f = by_rule[RULE_PROBLEM_STATED]
            tp_results.append(
                TaskPointResult(
                    pt,
                    kind,
                    'covered' if f.status == 'ok' else 'gap',
                    [f.span] if f.span else [],
                    f.note,
                )
            )
        elif kind == 'recommendations':
            need = max(min_n, 1)
            tp_results.append(
                TaskPointResult(
                    pt,
                    kind,
                    'covered' if len(recs) >= need else 'gap',
                    [r.sentence.span for r in recs],
                    f'{len(recs)} located, need {need}',
                )
            )
        elif kind == 'reason':
            tp_results.append(
                TaskPointResult(
                    pt,
                    kind,
                    'covered' if recs and (not missing_reason) else 'gap',
                    [r.reason for r in recs if r.reason],
                    by_rule[RULE_RECOMMENDATION_REASON].note,
                )
            )
        elif kind == 'effect':
            tp_results.append(
                TaskPointResult(
                    pt,
                    kind,
                    'covered' if recs and (not missing_effect) else 'gap',
                    [r.effect for r in recs if r.effect],
                    by_rule[RULE_RECOMMENDATION_EFFECT].note,
                )
            )
        elif kind == 'reader':
            f = by_rule[RULE_READER_ADDRESSED]
            tp_results.append(
                TaskPointResult(
                    pt,
                    kind,
                    'covered' if f.status == 'ok' else 'gap' if f.status == 'gap' else 'unknown',
                    [f.span] if f.span else [],
                    f.note,
                )
            )
        else:
            tp_results.append(
                TaskPointResult(
                    pt, 'unknown', 'unknown', [], 'no deterministic check for this point'
                )
            )
    return ProposalAnalysis(
        PROPOSAL_CHECKS_VERSION,
        word_count,
        headings,
        sentences,
        recs,
        findings,
        tp_results,
        terms,
        announcements,
    )
