# EP-ARCH-04.3 — Transaction Boundary Ownership

## Mục tiêu

Khóa contract transaction ownership sau khi hoàn tất service → RepositoryProvider boundary:

- Application service owns `commit()` / `rollback()`.
- Repository chỉ thực hiện persistence/query operations và không tự commit/rollback.
- RepositoryProvider chỉ tạo repository, không điều khiển transaction.

## Rationale

Nếu repository tự commit, một application operation có nhiều repository có thể bị commit từng phần. Điều đó phá vỡ atomicity của service-level use case và làm transaction policy phụ thuộc vào implementation detail của persistence adapter.

## Regression gate

`tests/test_ep_arch_04_3_transaction_boundary.py` kiểm tra source-driven:

1. Concrete repositories không gọi `.commit()` hoặc `.rollback()`.
2. Service không giao transaction control cho repository/provider objects.
3. Service tree vẫn có service-owned `session.commit()` / `session.rollback()` sites, tránh việc refactor nhầm transaction ownership xuống repository.

## Non-goals

- Không thay đổi transaction policy hiện tại.
- Không giới thiệu Unit of Work mới.
- Không refactor business services trong task này.
- Không thay đổi repository API.
