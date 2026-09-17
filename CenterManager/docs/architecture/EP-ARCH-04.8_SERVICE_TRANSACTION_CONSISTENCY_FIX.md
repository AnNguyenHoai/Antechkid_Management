# EP-ARCH-04.8 follow-up — rollback detection correction

The EP-ARCH-04.8 gate must recognize the established application-owned SQLAlchemy session context (`with session_factory() as session:`) as an exception-safe rollback boundary. Existing service methods use this pattern extensively, so requiring a literal `session.rollback()` in every committing method would produce false positives and force unnecessary business-code rewrites.

The gate should therefore accept either an explicit exception-handler rollback or a session-factory context manager enclosing the commit. Repository transaction ownership remains forbidden.
