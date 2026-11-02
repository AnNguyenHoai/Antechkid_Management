# QA-P0-02 — Execution results

Source baseline pinned: `470b7385d60d776bde8e555396520a71fd99c9b9`.
Existing CI #830 reported PASS in task handover; not independently used as evidence of R2 security.
New source: `tests/test_qa_p0_02_r1_git_attacks.py`, 9 parametrized cases (5 direct-bypass cases + 4 other tests).
**At authoring:** executed 0; PASS 0; FAIL 0; R1 NOT RUN 9; R2 BLOCKED 18. No actual R2 staging remote is known. No product defect has been empirically demonstrated against production.

R1 tests characterize an intentionally unprotected bare remote and should PASS when invalid ownership still permits direct push; these are security-negative demonstrations, not security acceptance. R2 must be separately verified. CI green alone is insufficient. **Release recommendation: NOT VERIFIED / HOLD.**
