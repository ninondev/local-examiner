# Copyright (c) 2026 Ninon
# SPDX-License-Identifier: MPL-2.0
"""Deterministic checks and revision memory for English proposals."""
from .capsule import Capsule, capsule_from_revision
from .local_examiner import ExaminerReport, examine, narrate
from .proposal_checks import ProposalAnalysis, RULE_IDS, analyse_proposal
from .textnorm import canon_json, hexify_floats

__all__ = ["Capsule", "ExaminerReport", "ProposalAnalysis", "RULE_IDS", "analyse_proposal",
           "canon_json", "capsule_from_revision", "examine", "hexify_floats", "narrate"]
__version__ = "0.1.0"
