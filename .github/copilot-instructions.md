# GitHub Copilot Agent Instructions for DB_LIBRARY_EDIT

*Version: 1.0 | Updated: 2026-04-10*

> **Note**: Những hướng dẫn này implement toàn bộ **13 quy tắc nền tảng** từ [WORKSPACE_RULES.md](../00_admin/WORKSPACE_RULES.md). Xem file đó để biết chi tiết đầy đủ.

## Agent Behavior Guidelines

Khi làm việc trong workspace DB_LIBRARY_EDIT, Copilot/Agent phải tuân thủ những hướng dẫn sau:

### 1. Workspace Structure
- ✓ Làm việc theo cấu trúc workspace hiện có (không tự ý thay đổi)
- ✓ Tôn trọng ranh giới giữa Library (chính thức) và Test (thử nghiệm)
- ✓ Không gộp hay di chuyển nội dung giữa `IBST_Materials_Library` và `IBST_Materials` mà không có mapping rõ ràng
- ✓ Khi thêm workspace con mới, thử mirror cấu trúc của workspace hiện có

### 2. File Naming & Versioning
- ✓ Không tự ý đổi tên file `.ddf` hay `.cdt` (chúng là DesignBuilder artifacts)
- ✓ Nếu phải replace file, backup lại bản cũ với hậu tố `.bak_YYYYMMDD_HHMMSS`
- ✓ Tuân thủ quy ước đặt tên trong `NAMING_CONVENTIONS.md`
- ✓ Folder routing sử dụng prefix số: 00_, 01_, ..., 99_

### 3. Data Integrity
- ✓ Không xóa file dữ liệu (`.ddf`, `.cdt`, `.csv`, `.txt` data files) mà không có lý do rõ ràng
- ✓ Luôn kiểm tra trùng lặp trước ghi file (compare nội dung trước overwrite)
- ✓ Nếu phát hiện file đích đã tồn tại với nội dung khác → backup + ghi mới, không ghi đè mù quáng
- ✓ Source/reference files (\_baseline\_analysis.txt, \_seed\_analysis.txt) là read-only về quy trình

### 3b. File Replacement & In-place Update
- ✓ Khi chỉnh sửa file có sẵn, **sửa trực tiếp và replace file cũ** (in-place update)
- ✓ **KHÔNG tạo file song song** như _new, _fixed, _v2, _updated, _final, copy, temp
- ✓ Chỉ được tạo file mới nếu:
  1. Người dùng yêu cầu rõ ràng
  2. File đích chưa tồn tại (tạo mới lần đầu)
  3. Ràng buộc kỹ thuật cần file trung gian (nhưng cleanup sau)
- ✓ Nếu cần backup, dùng `.bak_YYYYMMDD_HHMMSS` (file phụ trợ, không coi là output)
- ✓ Nếu tạo file tạm → thay thế lại file cũ → xóa file tạm, không để rác

### 4. Change Policy
Tuân thủ CHANGE_POLICY.md:
- ✓ **SOURCE/REFERENCE**: Cấm sửa, chỉ tham khảo
- ✓ **INPUT/TEMPLATE**: Sửa được nhưng phải backup nếu thay đổi lớn
- ✓ **WORKING_DATA**: Sửa tự do, nhưng track thay đổi (WORK_NOTES)
- ✓ **BUILD_CANDIDATES**: Không sửa trực tiếp, rebuild từ source nếu cần thay đổi

### 5. Reporting & Documentation
- ✓ Sau mỗi reorganize, build, test, hoặc patch lớn → tạo report ngắn
- ✓ Ghi rõ: ngày giờ, tác vụ, file thay đổi, kết quả, nhận xét
- ✓ Report được lưu trong `00_admin/REPORT_TEMPLATES/` hoặc `xx_reports/` của workspace con
- ✓ Ưu tiên tiếng Việt cho documentation, tiếng Anh cho code

### 6. Python & Scripts
- ✓ Dùng Python environment chung tại `DB_LIBRARY_EDIT/.venv/` (không tạo venv rời rạc)
- ✓ Script phải có: logging, error handling, idempotent nếu có thể
- ✓ Khi viết script, phải output log file hoặc stdout với kết quả rõ ràng (PASS/FAIL)
- ✓ Cài package mới phải cập nhật requirements.txt

### 7. Workflow & Process
- ✓ Làm theo luồng: source/reference → input → working → build → validation → release (xem WORKSPACE_FLOW.md)
- ✓ Không bỏ qua bước validation mà không có lý do rõ ràng
- ✓ Test import (nếu có DesignBuilder) trước khi coi là pass

### 8. Uncertainty & Escalation
- ✓ **Khi không chắc**:
  - Hỏi trước khi sửa (tạo todo/issue trong DECISION_LOG.md hoặc text file)
  - Hoặc archive tạm sang `99_archive/temp/` thay vì sửa mù
  - Ghi chú lý do tại sao không chắc
- ✓ Từ chối sửa file SOURCE/REFERENCE trừ khi yêu cầu hiển thị rõ ràng

### 9. Git / Version Control
- ✓ Commit công việc lớn với message rõ ràng
- ✓ Tránh commit file trong `.venv/`, `__pycache__/`, `.pytest_cache/` (xem .gitignore)
- ✓ Đẩy changes định kỳ (không để quá lâu uncommitted)

### 10. VS Code / Development Environment
- ✓ Đảm bảo `.vscode/settings.json` trỏ Python interpreter về `.venv`
- ✓ Khuyến khích dùng extensions gợi ý trong `extensions.json`
- ✓ Tasks trong `tasks.json` sẵn sàng để setup environment, run tests

## Ví dụ quyết định

### Scenario 1: Phát hiện lỗi dữ liệu trong file source
❌ **SAI**: Sửa trực tiếp `_seed_analysis.txt`
✓ **ĐÚNG**:
  1. Ghi chú lỗi trong WORK_NOTES.md
  2. Tạo task trong DECISION_LOG.md
  3. Chờ approval trước sửa

### Scenario 2: Cần thay đổi BUILD_CANDIDATES
❌ **SAI**: Sửa trực tiếp file `.ddf`
✓ **ĐÚNG**:
  1. Quay lại WORKING_DATA (source rows)
  2. Sửa data source
  3. Chạy build script → tạo .ddf mới
  4. Backup .ddf cũ (.bak_...)

### Scenario 3: Tạo file mới
✓ **ĐÚNG quy trình**:
  1. Kiểm tra file đó chưa tồn tại
  2. Tạo file mới
  3. Nếu file đó đã tồn tại → compare nội dung
     - Giống nhau? → skip
     - Khác nhau? → backup cũ, ghi mới

### Scenario 4: Không chắc file thuộc loại nào
✓ **ĐÚNG**:
  1. Archive tạm sang `99_archive/temp/`
  2. Ghi chú trong text file tại sao archive
  3. Hỏi confirmation sau

## Command Reference

### Setup environment lần đầu (PowerShell/Bash)
```bash
# PowerShell
.\scripts\setup_python_env.ps1

# Bash
bash scripts/setup_python_env.sh
```

### Activate environment
```bash
# PowerShell
.\.venv\Scripts\Activate.ps1

# Bash
source .venv/bin/activate
```

### Run smoke test
```bash
python scripts/smoke_test.py
```

### Cài package mới
```bash
pip install <package_name>
pip freeze > requirements.txt
```

---

**Key takeaway**: Safety first, report always, ask when uncertain.
