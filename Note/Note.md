python -m venv .venv
.\.venv\Scripts\activate

--> cai dat moi truong ao
============================================
rm runtime/Database/center.db
 ---> xóa database để test

rm migrations/versions/*.py
 --> xóa các migration version db


touch migrations/versions/__init__.py
->>>giữ lại file init

alembic revision --autogenerate -m "initial_schema"
---> tạo ra db

Nếu bạn muốn giữ dữ liệu hiện có (không reset)
Sửa file migrations/versions/4_update_assessment_table.py, đổi down_revision thành revision hiện có (ví dụ '2_add_occupation_to_parents' nếu file 3_add_timeline_columns bị mất). Kiểm tra danh sách file trong migrations/versions/ để biết chính xác tên revision đang có.

python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
pip install -r requirements-dev.txt  # optional for testing
python run.py
============================================
pytest -> chay cac test

===========================================
===========================================
C:\Python314\python.exe -m pip install -r requirements-dev.txt 
--> cai dat moi truong can thiet
===========================================
Cai dat alembic trong moi truong ao
pip install alembic

===========================================

Current status:
27/7: gửi task từ gpt sang deepseek, deepseek đã làm xong và chưa copy code vào repo -> tiếp theo cần copy code và repo, chạy được và gửi cho gpt review

28/7: GPT đã review xong, tiếp theo sẽ giao tiếp với GPT để có định hướng tiếp theo
28/7: Deepseek mới fix bug xong, chưa copy bản fix vô code, tiếp theo cần copy vô code rồi test

4/8: Đã yêu cầu deepseek code để deploy, chưa merge vào

-> tiếp theo cần làm export học sinh, trao đổi tiếp với GPT để làm

5/8: đã xong clean up, tiếp theo sẽ làm engine build

6/8: set up git thành công. quay lại GPT để review và làm tiếp

B1. vào runtime/Config điền thông tin, token thì lên git hub -> mở setting(user) -> tạo token mới -> cấp quyền
B2. tạo file read me và commit đầu tiên


6/8: đang kiểm tra và fix vài lỗi, quay lại thì check lỗi rồi fix tiếp

10/8: Lỗi no key vẫn chưa xử lý được, tiếp đến cần làm việc với Deepseek để fix

- Đã chạy được, đã hỏi deepseek về upload ảnh nhuwgn chưa copy vào, tiếp theo sẽ test key


- Quay lại làm thì vô GPT để yêu cầu đưa sprint 12 để làm tiếp