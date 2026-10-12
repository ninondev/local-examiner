# Copyright (c) 2026 Ninon
# SPDX-License-Identifier: MIT
"""Complete outputs for the synthetic demo, with fixed capsule metadata."""
from local_examiner import canon_json, demo, examine, hexify_floats, narrate


def snapshot_bytes():
    cap = demo.make_demo_capsule()
    kw = dict(task_text=demo.TASK_WORKSHOP, capability_id=demo.CAPABILITY,
              reader_terms=["events officer", "officer"])
    plain = examine(demo.NEW_WORKSHOP, capsules=[], **kw)
    remembered = examine(demo.NEW_WORKSHOP, capsules=[cap], **kw)
    return canon_json(hexify_floats({
        "fixture_kind": "synthetic", "capsule": cap.to_dict(),
        "plain": plain.to_dict(), "remembered": remembered.to_dict(),
        "plain_narration": narrate(plain), "remembered_narration": narrate(remembered),
        "demo": demo.run_demo()}))
