# DB_LIBRARY_EDIT - Quy ước đặt tên

Cập nhật: 2026-07-06

## Nguyên tắc chung

Tên file và thư mục cần giúp người dùng biết ngay:

- File thuộc nhóm dữ liệu nào.
- File đang ở bước nào trong quy trình.
- File là dữ liệu nguồn, dữ liệu làm việc, output build, log test hay tài liệu quản trị.

Không đổi tên file dữ liệu DesignBuilder nếu tên đó đang ảnh hưởng đến import/mapping.

## Thư mục điều hướng

Các workspace con nên dùng prefix số để dễ sắp xếp:

```text
00_admin/              quản trị nội bộ workspace con nếu cần
00_overview/           tổng quan, status, README con
01_reference_analysis/ dữ liệu gốc, baseline, seed, reference
02_input_samples/      CSV mẫu, template, schema mô tả input
03_row_working/        dữ liệu đang chỉnh sửa hoặc patch
04_build_candidates/   output ứng viên, thường là .ddf/.cdt
05_import_tests/       kết quả import thử, checklist, log
06_reports/            ghi chú, so sánh, báo cáo
99_archive/            dữ liệu cũ còn cần giữ
```

Quy tắc:

- Dùng 2 chữ số: `01_`, không dùng `1_`.
- `00_` dành cho admin/overview.
- `99_` dành cho archive.
- Tên sau prefix dùng chữ thường hoặc snake_case tùy phong cách sẵn có của workspace.

## File DesignBuilder

Các file `.ddf` và `.cdt` là artifact nhạy cảm.

Nguyên tắc:

- Không đổi tên nếu chưa hiểu mapping import.
- Không sửa tay nội dung nếu file được sinh từ script/build process.
- Nếu cần bản mới, tạo qua quy trình build hoặc xuất lại từ DesignBuilder.

Ví dụ tên hợp lệ:

```text
Materials.DDF
Materials_FULL_REBUILT.ddf
Glazing_TEST_MINI.ddf
Construction_TEST_MINI.cdt
```

## File báo cáo và log

Nên dùng tên rõ nghĩa:

| Loại file | Tên gợi ý |
| --- | --- |
| Tổng quan | `README.md`, `TEST_README.md` |
| Trạng thái | `STATUS.md`, `TEST_STATUS.md` |
| Checklist | `CHECKLIST.md`, `TEST_CHECKLIST.md` |
| Log import | `IMPORT_LOG.md` |
| So sánh build | `BUILD_COMPARE_NOTES.md` |
| Ghi chú làm việc | `WORK_NOTES.md` |
| Lịch sử thay đổi | `CHANGELOG.md` |

Nội dung tài liệu quản trị ưu tiên tiếng Việt. Tên file kỹ thuật có thể dùng tiếng Anh để dễ dùng với script/tool.

## File script và config

| Loại file | Quy ước | Ví dụ |
| --- | --- | --- |
| Python script | `snake_case.py` | `smoke_test.py` |
| PowerShell script | tên rõ nghĩa `.ps1` | `setup_python_env.ps1` |
| Bash script | `snake_case.sh` | `setup_python_env.sh` |
| Requirements | tên chuẩn pip | `requirements.txt`, `requirements-dev.txt` |
| Environment example | `.env.example` | `.env.example` |

## Backup và file tạm

Nếu cần backup trước khi sửa file quan trọng:

```text
file_name.ext.bak_YYYYMMDD_HHMMSS
```

Tránh để lại các file sau nếu không có lý do rõ:

```text
*_new.*
*_fixed.*
*_updated.*
*_final.*
*_v2.*
copy_*
temp_*
```

## Cấu trúc root hiện tại

```text
DB_LIBRARY_EDIT/
|-- .env.example
|-- .gitignore
|-- AGENTS.md
|-- README.md
|-- requirements.txt
|-- requirements-dev.txt
|-- 00_admin/
|-- .github/
|-- .vscode/
|-- scripts/
|-- IBST_Materials/
|-- IBST_Glazing/
`-- IBST_Construction/
```

`IBST_Materials_Library` đã được xóa và không còn là một phần của cấu trúc hiện tại.
