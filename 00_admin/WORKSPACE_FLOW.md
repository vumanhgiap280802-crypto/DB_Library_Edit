# DB_LIBRARY_EDIT - Luồng công việc chuẩn

Cập nhật: 2026-07-06

## Tổng quan

Workspace này hỗ trợ chuẩn bị, kiểm thử và quản lý dữ liệu thư viện DesignBuilder. Luồng chung áp dụng cho các workspace con như `IBST_Materials_Test`, `IBST_Glazing_Test` và `IBST_Construction_Test`.

```text
01 Source / Reference
-> 02 Input / Templates
-> 03 Working Data
-> 04 Build Candidates
-> 05 Validation / Import Test
-> 06 Reports / Controlled Release
-> 99 Archive
```

Không phải workspace nào cũng cần đủ toàn bộ các bước. Với workspace chỉ đang ở mức skeleton hoặc chưa có dữ liệu nguồn, có thể chỉ có tài liệu, checklist và report.

## 01 Source / Reference

Mục đích: giữ dữ liệu gốc, baseline, seed, database tham chiếu hoặc tài liệu xuất từ DesignBuilder.

Nguyên tắc:

- Đọc và tham khảo là chính.
- Không sửa trực tiếp nếu chưa có yêu cầu rõ.
- Nếu phát hiện lỗi, ghi chú vào report/work notes.

Ví dụ:

- File phân tích baseline/seed.
- `.ddf/.cdt` tham chiếu.
- CSV hoặc TXT xuất từ nguồn đáng tin cậy.

## 02 Input / Templates

Mục đích: giữ sample input, template CSV, mô tả schema hoặc dữ liệu mẫu để tạo bản mới.

Nguyên tắc:

- Có thể cập nhật khi format thay đổi.
- Nếu thay đổi lớn, ghi lý do trong report.
- Không trộn template của Materials, Glazing và Construction nếu format khác nhau.

## 03 Working Data

Mục đích: nơi chỉnh sửa, thử nghiệm, patch dữ liệu trước khi build.

Nguyên tắc:

- Có thể thay đổi linh hoạt hơn source/reference.
- Nên ghi chú các patch quan trọng.
- Không để file tạm hoặc bản `_final/_new/_v2` tồn tại lâu nếu không cần.

## 04 Build Candidates

Mục đích: chứa output ứng viên, thường là `.ddf/.cdt` hoặc file trung gian được tạo từ script/quy trình build.

Nguyên tắc:

- Không sửa tay nội dung build artifact.
- Nếu sai, quay lại working data hoặc script để build lại.
- Không đổi tên artifact nếu tên file đang phục vụ import vào DesignBuilder.

## 05 Validation / Import Test

Mục đích: kiểm tra dữ liệu trước khi coi là dùng được.

Các dạng kiểm tra:

- Kiểm tra cấu trúc file, số cột, encoding, schema.
- Import thử vào DesignBuilder.
- Ghi lại kết quả PASS/FAIL, lỗi và nhận xét.

Kết quả test nên nằm trong `05_import_tests` hoặc `06_reports` của workspace tương ứng.

## 06 Reports / Controlled Release

Mục đích: ghi lại trạng thái, kết quả, quyết định và thay đổi quan trọng.

Hiện tại chưa có workspace release chính thức trong root này. Vì vậy:

- `*_Test` chỉ là vùng kiểm thử.
- Không phát hành trực tiếp từ `*_Test` nếu chưa có quyết định riêng.
- Khi cần phát hành, tạo checklist/review rõ ràng trước khi công bố file.

## 99 Archive

Mục đích: giữ file cũ còn giá trị tra cứu nhưng không còn dùng thường xuyên.

Nguyên tắc:

- Chỉ archive những gì còn có giá trị lịch sử hoặc khôi phục.
- File rỗng, trùng lặp, hoặc đã chắc chắn không cần có thể xóa sau khi người dùng xác nhận.
- Archive nên có tên ngày/tháng hoặc lý do để dễ hiểu.

## Mapping workspace hiện tại

| Workspace | Vai trò hiện tại | Trạng thái |
| --- | --- | --- |
| `IBST_Materials_Test` | Kiểm thử dữ liệu vật liệu | Đang là workspace active |
| `IBST_Glazing_Test` | Kiểm thử dữ liệu kính/glazing | Đang là workspace active |
| `IBST_Construction_Test` | Kiểm thử dữ liệu construction | Đang là workspace active/skeleton tùy dữ liệu hiện có |

`IBST_Materials_Library` không còn tồn tại trong workspace hiện tại.

## Ghi log tối thiểu

Khi chuyển giữa các bước lớn, nên có ghi chú ngắn:

| Chuyển bước | File/log nên có | Nội dung tối thiểu |
| --- | --- | --- |
| Working -> Build | `BUILD_LOG.md` hoặc report liên quan | Ngày, input, script, output, lỗi nếu có |
| Build -> Validation | `IMPORT_LOG.md` hoặc checklist | File import, kết quả PASS/FAIL, ghi chú |
| Validation -> Release/Use | `CHANGELOG.md` hoặc `STATUS.md` | File được chấp nhận, lý do, phạm vi dùng |
