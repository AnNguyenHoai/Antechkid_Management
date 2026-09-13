# EP-ARCH-03.35 Batch E — ClassTimelineService Boundary Note

`ClassTimelineService` is explicitly provider-backed through `RepositoryProvider.class_timeline(...)`.

Database persistence is **repository-owned**. The service owns application-level transaction coordination, while the repository owns ORM persistence operations such as add and refresh.
