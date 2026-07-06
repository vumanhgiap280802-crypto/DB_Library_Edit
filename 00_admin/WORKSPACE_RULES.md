# DB_LIBRARY_EDIT - Quy tắc workspace chung

Cập nhật: 2026-07-06  
Phạm vi: root workspace `D:\Design Builder\DB_Library_Edit` và các workspace con hiện còn sử dụng.

## Mục đích

`DB_LIBRARY_EDIT` là workspace quản lý, kiểm thử và chuẩn hóa dữ liệu thư viện DesignBuilder. Trạng thái hiện tại tập trung vào các nhóm dữ liệu:

- `IBST_Materials`: kiểm thử dữ liệu vật liệu.
- `IBST_Glazing`: kiểm thử dữ liệu kính/glazing.
- `IBST_Construction`: kiểm thử dữ liệu kết cấu/construction.
- `scripts`: công cụ Python dùng chung.
- `00_admin`: tài liệu quản trị, quy tắc, quy ước và hướng dẫn môi trường.

`IBST_Materials_Library` đã được xóa khỏi workspace. Vì vậy hiện tại **chưa có workspace release chính thức** trong root này. Các workspace `IBST_Materials`, `IBST_Glazing` và `IBST_Construction` được xem là vùng kiểm thử/chuẩn bị dữ liệu, không tự động được coi là nguồn phát hành cuối.

## Quy tắc nền tảng

### Rule 01: Root workspace là vùng quản trị chung

- Không di chuyển tùy tiện root workspace hoặc các workspace con.
- Root chỉ giữ tài liệu quản trị, cấu hình, script dùng chung và README.
- Không lưu dữ liệu nghiệp vụ thô trực tiếp ở root nếu dữ liệu đó thuộc một workspace con cụ thể.

### Rule 02: Tách biệt từng workspace con

- Mỗi workspace con xử lý một nhóm dữ liệu riêng: Materials, Glazing, Construction.
- Không copy chéo dữ liệu giữa các workspace nếu chưa có lý do và mapping rõ ràng.
- Khi tái dùng logic giữa workspace, ưu tiên tái dùng script/quy trình, không trộn file dữ liệu.

### Rule 03: Chưa phát hành từ workspace test

- Các thư mục `IBST_Materials`, `IBST_Glazing` và `IBST_Construction` là nơi kiểm thử, đối chiếu, import thử và ghi nhận kết quả.
- Không coi file trong `IBST_Materials`, `IBST_Glazing` và `IBST_Construction` là bản phát hành chính thức nếu chưa có bước review/validation riêng.
- Nếu sau này cần release chính thức, nên tạo quy trình hoặc workspace release rõ ràng trước.

### Rule 04: Source/reference là read-only về quy trình

- Các file nguồn, baseline, seed, database tham chiếu hoặc tài liệu xuất từ DesignBuilder không được sửa trực tiếp.
- Nếu phát hiện lỗi trong source/reference, ghi chú vào report/work notes thay vì sửa ngay file gốc.
- Muốn thay đổi source/reference cần có yêu cầu rõ ràng và record lý do.

### Rule 05: Luồng xử lý có kiểm soát

Luồng chuẩn:

```text
source/reference
-> input/templates
-> working data
-> build candidates
-> validation/import test
-> report hoặc release có kiểm soát
```

Không bắt buộc workspace nào cũng có đủ mọi bước, nhưng nếu bỏ qua bước thì cần ghi rõ lý do trong tài liệu/report.

### Rule 06: Không sửa trực tiếp artifact DesignBuilder nhạy cảm

- Không chỉnh tay nội dung `.ddf`, `.cdt`, `.csv`, `.txt` nghiệp vụ nếu nhiệm vụ không yêu cầu rõ.
- Với `.ddf/.cdt`, ưu tiên sửa dữ liệu nguồn hoặc script tạo file rồi build lại.
- Không đổi tên `.ddf/.cdt` nếu tên file đang phục vụ import/mapping.

### Rule 07: Đặt tên và cấu trúc nhất quán

- Workspace con nên dùng prefix thư mục dạng `00_`, `01_`, `02_`, ..., `99_`.
- File báo cáo dùng tên rõ nghĩa như `STATUS.md`, `WORK_NOTES.md`, `IMPORT_LOG.md`, `CHANGELOG.md`.
- Chi tiết xem `NAMING_CONVENTIONS.md`.

### Rule 08: In-place update khi sửa tài liệu/config

- Khi sửa file đã tồn tại, mặc định sửa chính file đó.
- Không tạo các bản song song kiểu `_new`, `_fixed`, `_updated`, `_final`, `_v2` nếu không có lý do rõ.
- Nếu cần backup, dùng hậu tố `.bak_YYYYMMDD_HHMMSS`.

### Rule 09: Kiểm tra trước khi ghi hoặc xóa

- Trước khi ghi đè, kiểm tra file đích có tồn tại không.
- Trước khi xóa thư mục, xác nhận đường dẫn nằm trong workspace hiện tại.
- Không xóa dữ liệu nghiệp vụ nếu chưa có yêu cầu rõ từ người dùng.

### Rule 10: Ghi nhận thay đổi lớn

Các thay đổi sau nên được ghi lại trong README, report hoặc ghi chú commit:

- Thêm/xóa workspace con.
- Thay đổi quy trình build/import.
- Thay đổi môi trường Python hoặc dependencies.
- Xóa archive, artifact hoặc tài liệu quản trị.

### Rule 11: Ngôn ngữ tài liệu

- Tài liệu quản trị ưu tiên tiếng Việt.
- Tên file kỹ thuật, script và biến trong code có thể dùng tiếng Anh.
- README chính nên đủ rõ để người không biết code vẫn hiểu vai trò workspace.

## Vai trò hiện tại của 00_admin

`00_admin` là nơi giữ bộ quy tắc vận hành tối thiểu:

- `WORKSPACE_RULES.md`: quy tắc chung.
- `WORKSPACE_FLOW.md`: luồng công việc.
- `NAMING_CONVENTIONS.md`: quy ước đặt tên.
- `CHANGE_POLICY.md`: chính sách thay đổi file.
- `PYTHON_ENVIRONMENT.md`: hướng dẫn môi trường Python.

Không đặt parser, build script, source data hoặc kết quả import trong `00_admin`.

## Kiểm tra nhanh sau thay đổi

Các lệnh nên chạy khi cập nhật tài liệu quản trị:

```powershell
# Tìm lại các cụm từ khóa cũ nếu cần đối chiếu tài liệu.
$env:PYTHONIOENCODING='utf-8'
python .\scripts\smoke_test.py
```

Nếu smoke test không chạy được do thiếu package hoặc môi trường Python, cần ghi rõ trạng thái trong báo cáo công việc.
