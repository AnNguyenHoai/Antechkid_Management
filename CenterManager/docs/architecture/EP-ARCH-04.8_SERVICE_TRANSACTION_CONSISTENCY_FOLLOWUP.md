# EP-ARCH-04.8 follow-up

The service transaction gate recognizes two valid exception-safe rollback boundaries: an explicit rollback in an exception handler, or an application-owned SQLAlchemy session context (`with session_factory() as session:`) enclosing the commit. This avoids false positives for the established session lifecycle pattern.
