# local-examiner

I wanted to make a writing checker that remembers what you fixed last time.

If you made a mistake before and fixed it, local-examiner can show that old fix when the same problem comes back. It saves your old text and your revision, then brings them back when a rule finds a similar gap. It can also show which rules you fixed before and got right this time.

For now, it's a small tool for English proposal writing only. It checks your text with written rules, not an AI model. When it finds a gap, it can point to the sentence and its character position, so you can see what triggered the rule.

Everything runs locally. No LLM, no training, no network, and no extra runtime packages. I also wanted the output to be repeatable, even down to the bytes. There's more about that in [Determinism](#determinism).

This is not an exam scorer. It doesn't give you a grade or a C1 level. I haven't measured its precision, recall, or agreement with human raters yet. The rules are useful signals, not proof that your writing is good or bad.

## Quick start

You need Python 3.10 or later. From the repository folder, try this:

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

This is the real output:

```text
plain
['proposal.recommendation_has_effect']
```

The gap is there because the text has two recommendations but doesn't say what good results they will bring.

I turned off the word count check here with `word_range=None`, because this is only a short example. Normally, `examine()` checks for 220–260 words and at least two recommendations. You can change both.

If you need the report as canonical bytes:

```python
from local_examiner import canon_json, hexify_floats

report_bytes = canon_json(hexify_floats(report.to_dict()))
```

You can also build and install a wheel. The steps are in [CONTRIBUTING.md](CONTRIBUTING.md).

## Rules

Each finding has a rule ID and a status:

- `ok`: the rule found the signal it was looking for.
- `gap`: the rule found something missing.
- `info`: just a note, or the rule doesn't apply here.

It also includes evidence when the tool can find it.

| Rule ID | What it looks for |
| --- | --- |
| `proposal.recommendation_count` | Are there enough recommended actions? |
| `proposal.recommendation_has_reason` | Is there a reason near each action, or in an earlier problem section? |
| `proposal.recommendation_has_effect` | Is there a result near each action, or in a later benefits section? |
| `proposal.problem_stated` | Is the problem mentioned near the start, outside the action parts? |
| `proposal.reader_addressed` | Is the named reader mentioned, or directly addressed in a reader line? |
| `proposal.future_orientation` | Do the actions use more past-time markers than future or modal markers? |
| `proposal.headings_used` | Does the text have section headings? Missing headings alone aren't a gap. |
| `proposal.contractions` | Are there short forms like `it's` or `can't`? |
| `proposal.word_range` | Is the text within the chosen word range? |
| `proposal.letter_frame` | Is there a greeting or letter ending? Missing one isn't a gap. |

A few details: words are counted by spaces, including headings. A text up to 10% below the minimum or 15% above the maximum gets an `info` note for its length. These are choices I made for the rules, not numbers proved by a study.

The checker can look for a problem, actions, reasons, effects, and the reader in task points. Other task points are marked `unknown`.

## Precedent capsules

A capsule keeps an earlier piece of writing, your revised version, and the rules that changed. When you check a new proposal, the tool can find an old fix for a problem that came back. It can also show what you fixed before and still got right, so it doesn't need to remind you again.

Try the synthetic before-and-after demo:

```sh
python3 -m local_examiner.demo
```

These are real lines from the output:

```text
[mode: capsule] 1 capsule(s) retrieved; 2 recurring gap(s), 1 rule(s) kept.
Kept from last time (no reminder needed): proposal.reader_addressed
Focus next: proposal.recommendation_has_effect
```

To make your own capsule, use `capsule_from_revision()`. Give it `capability_id`, `task_id`, `prompt_text`, `before_text`, and `after_text`.

If you want fixed metadata, set `issued_at` and `capsule_id` yourself. Then pass the saved capsule to `examine(..., capsules=[capsule])`. The capability and rubric IDs must match the ones you used when creating it. Keep the UTC timestamp format the same for all capsules.

Reports also have `personal`, `kept`, `usage`, and `few_shot` fields. An optional narration layer can read `few_shot`, including `prior_outcome`, and explain what the report already says. It shouldn't add new judgments. There's no model included in this project.

## Determinism

I wanted to be able to run the same test twice and actually get the same result.

With the same library version, Python text rules, input text, options, and saved capsules, sequential calls return the same canonical bytes. The checking code doesn't use the clock or random numbers. JSON keys are sorted, and capsule float values are written in their exact binary64 hex form before the JSON is made.

There are a few things to watch:

- If you don't give `issued_at` or `capsule_id` when creating a capsule, it uses the current time or a random ID. Set both if you need repeatable capsule bytes.
- If you use an optional signer, it must also give the same output for the same input.

The tests cover fixed JSON and float bytes, capsule import and export, and retrieval order when scores tie. They also compare a full synthetic output file across eight fresh processes per Python version, changing hash seeds and locale settings.

All 27 tests pass on Python 3.11, 3.12, 3.13, and 3.14, on one Mac. I haven't tested another machine or Python 3.10 yet.

Run the tests with:

```sh
python3 -m unittest discover -s tests -v
```

Or, if you have pytest:

```sh
python3 -m pytest -q
```

## Limits

It's a rule-based checker for English proposals, not a general writing examiner. It looks at words and patterns, so sometimes it will miss a real action or find a signal that doesn't make sense in context. Finding a reason word doesn't mean the reason actually supports the recommendation.

And `ok` doesn't mean you've mastered a skill or reached C1. It only means that particular rule found its signal this time.

Please make calls one at a time. This version uses shared state while finding actions.

A few things about the saved capsules:

- Each capsule has a SHA-256 digest, and there are optional signing hooks. But a digest alone can't prove who created it.
- There's no signing library bundled. Check `verify_digest()` before checking a signature. Signature verification returns `None` if there is no signature or verifier. Only use capsules from sources you trust.
- Capsules may contain a learner's full writing. Be careful when saving or sharing them.

The capsule adapter can store scores you provide, but it doesn't score the writing itself. Its score window is a fixed range, not a measured confidence interval.

## License and contributions

The code is under the [MIT license](LICENSE). Pull requests are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.
