# STUDENT_SERVICE – CenterManager

## Student Lifecycle

CenterManager Student undergoes the following lifecycle:

1. **Create** – New Student is created with automatically generated code (e.g., HS001). Status defaults to ACTIVE.
2. **Update** – Editable fields: full_name, preferred_name, date_of_birth, gender, status, current_level, notes. Student code is permanent.
3. **Soft Delete** – Student is marked deleted (deleted_at = timestamp). Child records are preserved.
4. **Restore** – Deleted Student can be restored (deleted_at = NULL). Original student code is preserved.

## Student Code Rule

- Format: `HS` followed by a numeric portion (minimum 3 digits). 
- First student: `HS001`.
- Next code: highest existing HS code + 1 (including deleted students). Gaps are NOT filled.
- Legacy codes (e.g., `ABC`, `TEMP`) are ignored for generation but do not break the system.
- Codes are never reused.

Examples:
- Existing: `HS001, HS002, HS003` → Next: `HS004`
- Existing: `HS001, HS005` → Next: `HS006`
- Existing: `ABC, HS005, TEMP` → Next: `HS006`
- Existing: `HS999` → Next: `HS1000`

## Service API

### `create_student(full_name, ...) -> Student`
- Required: `full_name` (non-empty, normalized).
- Optional: `preferred_name`, `date_of_birth`, `gender`, `status`, `current_level`, `notes`.
- Status defaults to `ACTIVE`.
- Generates student code automatically.

### `get_student(student_id) -> Student`
- Returns active Student (deleted_at IS NULL). Raises `StudentNotFoundError` if not found or deleted.

### `get_student_by_code(student_code) -> Student`
- Same as above but by student_code.

### `get_student_including_deleted(student_id) -> Optional[Student]`
- Returns Student even if deleted, or None.

### `list_students() -> List[Student]`
- Returns all active students, sorted by student_code ascending.

### `update_student(student_id, ...) -> Student`
- Only supplied fields are updated.
- `student_code` cannot be changed.
- `full_name` cannot be blank.

### `delete_student(student_id) -> None`
- Soft-delete: sets `deleted_at = now()`. Raises if already deleted or not found.

### `restore_student(student_id) -> None`
- Restores soft-deleted Student: sets `deleted_at = NULL`. Raises if not deleted or not found.

## Business Exceptions

- `StudentNotFoundError` – Student does not exist or is deleted.
- `StudentValidationError` – Invalid input (e.g., blank full_name).
- `StudentAlreadyDeletedError` – Attempt to delete already-deleted Student.
- `StudentNotDeletedError` – Attempt to restore active Student.

## Transaction Ownership

Service owns all transaction boundaries. Each method creates its own session, commits on success, rolls back on failure. The caller (UI) does not manage sessions.

## Service vs Repository

- **Service**: Business rules, validation, code generation, transaction management.
- **Repository**: Persistence queries, ORM operations only.

## Partial Update Semantics

`update_student()` uses a sentinel value `UNSET` to distinguish between:

- **Field not supplied** → preserve existing value.
- **`None`** → explicitly clear nullable field (set to NULL).
- **Other value** → update field with normalized value.

Nullable fields: `preferred_name`, `date_of_birth`, `gender`, `current_level`, `notes`.

`full_name` is required and cannot be cleared.