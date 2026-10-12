# local-examiner


A writing checker that remembers. When a learner repeats a mistake they fixed before, it puts the old fix next to the new sentence.

It checks English proposal writing against explicit rules and quotes the exact sentence and character position for each gap. It needs no training, no LLM, no network and no runtime packages. The same input gives the same bytes on every run: in 16 fresh processes (four hash seeds, two locales), the full output matched one saved file exactly. The test suite passes 27 tests on Python 3.13 and 3.14.

Limits: it covers the proposal genre only, in English only, and it gives no exam score. No one has measured its rule precision, recall or agreement with human raters yet.

## Quick start

Use Python 3.10 or later. Run this from the repository folder:

```python
from local_examiner import examine

# Synthetic example. This is not an exam task or a sample answer.
text = """To: The Manager
Current situation
At present the hall is underused.
Recommendations
First, install new lamps.
Second, add a notice board."""

report = examine(
    text,
    capability_id="proposal.clear_actions",
    reader_terms=["manager"],
    word_range=None,
)
print(report.mode)
print([gap["rule_id"] for gap in report.generic_gaps])
```

Real output:

```text
plain
['proposal.recommendation_has_effect']
```

The two actions have no stated result. This short example turns off the length
check with `word_range=None`. By default, `examine()` uses a 220 to 260 word range
and looks for at least two recommendations. You can change both settings.

For canonical report bytes:

```python
from local_examiner import canon_json, hexify_floats

report_bytes = canon_json(hexify_floats(report.to_dict()))
```

You can also build and install a wheel. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Rules

Each finding has a rule ID, a status, and evidence when it can be found.
`ok` means a signal was found. `gap` means a rule found a missing part.
`info` means the result is only a note or the check does not apply.

| Rule ID | What it checks |
| --- | --- |
| `proposal.recommendation_count` | Counts action units against the chosen minimum. |
| `proposal.recommendation_has_reason` | Looks for a reason near each action or in an earlier problem section. |
| `proposal.recommendation_has_effect` | Looks for a stated result near each action or in a following benefits section. |
| `proposal.problem_stated` | Looks for problem words in the early part of the text, outside action units. |
| `proposal.reader_addressed` | Looks for a supplied reader name, or a reader line with direct address. |
| `proposal.future_orientation` | Flags more past markers than future or modal markers in action units. |
| `proposal.headings_used` | Notes section headings; missing headings alone do not create a gap. |
| `proposal.contractions` | Flags short forms such as `it's` and `can't`. |
| `proposal.word_range` | Checks a word range; slightly short or long texts get an info note. |
| `proposal.letter_frame` | Notes a greeting or letter ending; this rule does not create a gap. |

Words are counted by spaces, including headings. The length check gives an
info note for counts below the minimum by up to 10%, or above the maximum by
up to 15%. These are fixed rule choices, not measured accuracy numbers.
Task points can be checked for a problem, actions, reasons, effects, and reader.
Other task points are marked `unknown`.

## Precedent capsules

A capsule saves an earlier text, its revision, and the rules that changed.
On a new proposal, the examiner can link a recurring gap to that fix and show
which previously fixed rules the learner kept.

Run the synthetic before-and-after demo:

```sh
python3 -m local_examiner.demo
```

The capsule result includes these real lines:

```text
[mode: capsule] 1 capsule(s) retrieved; 2 recurring gap(s), 1 rule(s) kept.
Kept from last time (no reminder needed): proposal.reader_addressed
Focus next: proposal.recommendation_has_effect
```

Create a capsule with `capsule_from_revision()`. Supply your own
`capability_id`, `task_id`, `prompt_text`, `before_text`, and `after_text`.
Use `issued_at` and `capsule_id` for fixed metadata. Pass the saved capsule in
`examine(..., capsules=[capsule])`. Match the capability and rubric IDs used
when you made it. Use the same UTC time format for all capsules.

The report has `personal`, `kept`, `usage`, and `few_shot` fields.
An optional narration layer can read `few_shot`, including `prior_outcome`.
It should explain these facts and add no new judgments. No model is included.

## Determinism

For the same library version, Python text rules, text, options, and saved
capsules, sequential calls return the same canonical bytes. The check itself
uses no clock or random values. JSON keys are sorted. Floats in capsule data
use their exact binary64 hex values before JSON is written.

Creating a capsule without `issued_at` or `capsule_id` uses the current time
or a random ID. Supply both when you need repeatable capsule bytes.
An optional signer must also give stable output for identical input.

Tests check fixed JSON and float bytes, capsule import and export, and
retrieval order when scores tie. A full synthetic output file is checked
against eight fresh processes per Python version. Hash seeds and locale
settings change between those processes. All runs were on one Mac;
other devices and Python 3.10 to 3.12 have not been tested.

```sh
nice -n 10 python3 -m unittest discover -s tests -v
```

If pytest is installed, use `nice -n 10 python3 -m pytest -q`.

## Limits

These are English word and pattern rules for the proposal genre only.
They can miss a valid action or find a signal that does not fit the meaning.
A reason signal does not prove that the reason supports the action.
A current `ok` result does not prove lasting mastery or a C1 level.
Make calls one at a time; this version uses shared state while finding actions.

Capsules have a SHA-256 digest and optional signing hooks. A digest alone
cannot prove who issued a capsule. No signing library is bundled. Check
`verify_digest()` before checking a signature. Signature verification returns
`None` if no signature or verifier is present. Use trusted capsule input.
Capsules can contain full learner texts. Store and share them with care.

The capsule adapter can store scores supplied by a caller. It does not grade
the text. Its score window is a fixed range, not a measured confidence interval.

## License and contributions

The code is under [MPL-2.0](LICENSE). Pull requests are welcome.
See [CONTRIBUTING.md](CONTRIBUTING.md) and [CLA.md](CLA.md) before contributing.

If this was useful to you, a star helps other people find it.
