# QA-P0-02 — Publication path and enforcement audit (preliminary)
Source snapshot: `main_repos@470b7385d60d776bde8e555396520a71fd99c9b9`.

## Verified source evidence
- `GitSynchronizationProvider` has direct Git subprocess execution, client-held token setup via `GitCredentialHelper`, separate `lock-main`/`queue-main` and MAIN refs; these are not by themselves server-side authorization.
- `WriteTransactionManager` reports FINISHING state and MAIN optimistic concurrency; its own documentation names CLIENT-side fencing and generation protection.
- `WRITE_AUTHORITY_FENCING_CONTRACT.md` explicitly says **PROPOSED / NOT IMPLEMENTED** and that legacy desktop-held credentials allowing ordinary MAIN pushes can bypass proposed cooperative multi-ref CAS.
- E1B-2B local mutation gate protects application-owned SQLCipher mutation, not an arbitrary `git push` issued by a legacy executable.
- Older QA #533 tests exercise local Git CAS, atomic two-ref and recovery; they do not establish R2 credential rejection.

## Publication boundaries requiring deeper path trace
`GitSynchronizationProvider.publish_only`, push helpers, startup/recovery publishing, backup/CLI tools, legacy EXE embedded credentials, direct provider invocation and actual GitHub branch rules. Source and documentation imply an R1 bypass, but actual GitHub protection and credential scope were NOT inspected through authenticated administration. No change to live settings or secrets.

## Preliminary security exposure
**P0 architectural release blocker (not a proven incident):** a legacy or manual Git client holding an authorized ref-update credential can submit a valid FF update to MAIN without consulting current WRITE session/lease. A changed lock ref without a changed MAIN does not create a MAIN-level Git conflict. Demonstrate with R1 test then check R2; R2 unavailable => BLOCKED.

## Required R2 proof
Use entirely separate staging credentials and a staging remote with equivalent server rules. Attempt direct MAIN update using retired token, READ token, downgraded client and old session; record auth reject and unchanged MAIN. Confirm that accepted publication and authority update linearize at one server-enforced point. Never test attack against production.
