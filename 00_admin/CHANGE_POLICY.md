# DB_LIBRARY_EDIT - Chính sách thay đổi

Cập nhật: 2026-07-06

## Mục đích

Chính sách này giúp tránh mất dữ liệu, sửa nhầm artifact DesignBuilder, hoặc để lại nhiều bản file gây khó hiểu.

Áp dụng cho root workspace và các workspace con:

- `IBST_Materials`
- `IBST_Glazing`
- `IBST_Construction`

## Phân loại file

### 1. Source / Reference

Ví dụ:

- File baseline/seed/reference.
- File `.ddf/.cdt` dùng làm tham chiếu.
- File xuất từ DesignBuilder để phân tích.

Chính sách:

- Không sửa trực tiếp nếu chưa có yêu cầu rõ.
- Không xóa nếu chưa được xác nhận.
- Được phép đọc, copy để phân tích, hoặc tạo bản working riêng.
- Nếu phát hiện lỗi, ghi chú vào `WORK_NOTES.md`, `STATUS.md` hoặc report phù hợp.

### 2. Input / Template

Ví dụ:

- CSV mẫu.
- File mô tả schema.
- Template nhập liệu.

Chính sách:

- Có thể sửa khi format hoặc yêu cầu nhập liệu thay đổi.
- Nếu thay đổi lớn, ghi lại lý do.
- Không trộn template giữa Materials, Glazing và Construction nếu schema khác nhau.

### 3. Working Data

Ví dụ:

- Dòng dữ liệu đang chỉnh sửa.
- Patch đang thử nghiệm.
- File trung gian trước khi build.

Chính sách:

- Có thể sửa linh hoạt.
- Nên dọn file tạm sau khi xác nhận kết quả.
- Nên ghi chú các thay đổi có ảnh hưởng tới build/import.

### 4. Build Candidates

Ví dụ:

- `.ddf/.cdt` được tạo để import thử.
- Output từ script build.

Chính sách:

- Không sửa tay nội dung artifact.
- Không đổi tên nếu tên file phục vụ import/mapping.
- Nếu cần sửa, quay lại working data hoặc script rồi build lại.
- Có thể xóa build cũ khi người dùng xác nhận và đã có bản thay thế rõ ràng.

### 5. Validation / Import Logs

Ví dụ:

- `IMPORT_LOG.md`
- `TEST_CHECKLIST.md`
- `BUILD_COMPARE_NOTES.md`

Chính sách:

- Ghi thêm kết quả test mới.
- Không xóa lịch sử test còn giá trị.
- Có thể dọn log rỗng hoặc log lỗi thời nếu đã được xác nhận.

### 6. Reports / Documentation

Ví dụ:

- `README.md`
- `WORKSPACE_RULES.md`
- `WORKSPACE_FLOW.md`
- `NAMING_CONVENTIONS.md`
- `PYTHON_ENVIRONMENT.md`

Chính sách:

- Được phép cập nhật để phản ánh trạng thái thật của workspace.
- Nên sửa trực tiếp file hiện có thay vì tạo bản song song.
- Nếu tài liệu lỗi thời và không còn giá trị lịch sử, có thể xóa sau khi người dùng xác nhận.

## Quy trình sửa file

Trước khi sửa:

1. Xác định file thuộc loại nào.
2. Kiểm tra file có đang là source/reference hoặc artifact DesignBuilder không.
3. Nếu thay đổi có thể làm mất dữ liệu, hỏi người dùng hoặc tạo backup.

Khi sửa:

1. Sửa đúng file cần thiết.
2. Không format lại file không liên quan.
3. Không refactor lan rộng nếu không phục vụ nhiệm vụ.

Sau khi sửa:

1. Chạy lệnh kiểm tra phù hợp.
2. Báo file đã sửa/xóa.
3. Báo rõ kiểm tra đã chạy được hay chưa.

## Backup

Khi cần backup:

```text
file_name.ext.bak_YYYYMMDD_HHMMSS
```

Backup chỉ là file phụ trợ. Không dùng backup làm output chính.

## Khi nào cần xác nhận trước

Cần người dùng xác nhận trước khi:

- Xóa source/reference.
- Xóa `.ddf/.cdt/.csv/.txt` nghiệp vụ.
- Xóa cả workspace con.
- Đổi tên artifact DesignBuilder.
- Thay đổi lớn cấu trúc workspace.

## In-place update

Mặc định sửa file cũ tại vị trí cũ. Không tạo bản song song kiểu:

```text
_new
_fixed
_updated
_final
_v2
copy
temp
```

Ngoại lệ hợp lệ:

- Người dùng yêu cầu tạo file mới.
- File đích chưa tồn tại.
- Cần file trung gian cho xử lý kỹ thuật, sau đó phải dọn.
- Cần backup an toàn trước thao tác rủi ro.
