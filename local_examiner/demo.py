# Copyright (c) 2026 Ninon
# SPDX-License-Identifier: MIT
"""New synthetic proposals and tasks. These are not published exam materials."""
from .capsule import capsule_from_revision
from .local_examiner import examine, narrate

CAPABILITY = "proposal.actionable_recommendations"
TASK_HALL = "Write a proposal for the manager about a quiet hall. The reader is the manager."
BEFORE_HALL = """Proposal: a quiet hall

Current situation
At present the hall is underused because the lamps are broken. Members have nowhere comfortable to read.

Recommendations
First, extend the opening hours on Tuesdays.
Second, install new lamps beside the chairs.

Conclusion
I hope the club will consider these ideas."""
AFTER_HALL = """Proposal: a quiet hall

To: The Manager
Current situation
At present the hall is underused because the lamps are broken. Members have nowhere comfortable to read.

Recommendations
First, extend the opening hours on Tuesdays, so that members can read after work.
Second, install new lamps beside the chairs, which would give members a brighter place to sit.

Conclusion
I hope you will consider these ideas."""
TASK_WORKSHOP = "Write a proposal for the events officer about weekend workshops. The reader is the events officer."
NEW_WORKSHOP = """Proposal: weekend workshops

To: The Events Officer
Current situation
At present the workshops are underused because the timetable is unclear. Visitors rarely attend the early sessions.

Recommendations
First, open a late session on Sundays.
Second, add new signs beside the entrance.

Conclusion
I hope you will consider these ideas."""


def make_demo_capsule():
    return capsule_from_revision(
        capability_id=CAPABILITY, task_id="hall-1", prompt_text=TASK_HALL,
        before_text=BEFORE_HALL, after_text=AFTER_HALL, reader_terms=["the manager", "manager"],
        issued_at="2026-01-01T00:00:00+00:00", capsule_id="synthetic-capsule-1", subject_key="synthetic-learner")


def run_demo():
    cap = make_demo_capsule()
    options = dict(task_text=TASK_WORKSHOP, capability_id=CAPABILITY, reader_terms=["events officer", "officer"])
    return "\n".join([
        "Synthetic proposal demo",
        f"capsule_id={cap.capsule_id} digest={cap.content_digest} signature={cap.signature_algorithm}",
        "PLAIN mode", narrate(examine(NEW_WORKSHOP, capsules=[], **options)), "",
        "CAPSULE mode", narrate(examine(NEW_WORKSHOP, capsules=[cap], **options))])


if __name__ == "__main__":
    print(run_demo())
