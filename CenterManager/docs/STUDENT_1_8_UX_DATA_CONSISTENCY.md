# STUDENT-1.8 — UX & Data Consistency

## Implemented
- Lifecycle filter covers Active, Archived and Deleted.
- Search operates on the current filtered base.
- Quick search matches student code/name and the advertised parent name/phone.
- Refresh clears stale bulk selection.
- Context-menu mutation actions are disabled in read-only mode.
- Advanced filter results remain the base for subsequent search/sort.
- Empty result state exposes a clear no-match explanation.

## Regression intent
These changes prevent UI controls from advertising unsupported behavior and prevent
selection/filter state from drifting away from the current data set.
