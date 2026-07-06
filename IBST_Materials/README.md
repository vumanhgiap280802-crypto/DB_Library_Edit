# IBST_Materials

Workspace nay duoc dung de phan tich va chuan hoa quy trinh tao vat lieu moi tu du lieu ben ngoai, sau do dong goi de import vao DesignBuilder.

## Muc tieu hien tai

- hieu format tham chieu cua DesignBuilder cho materials import
- doi chieu du lieu CSV ben ngoai voi format CDT/DDF
- chuan bi cho buoc tu dong hoa: CSV -> CDT -> DDF

## Cau truc hien tai

- `01_designbuilder_format/`
  Chua cac file tham chieu tu DesignBuilder va bo final QA hien co.
- `02_csv_input/`
  Chua file CSV dau vao va du lieu trung gian dang co.
- `03_output/`
  Danh cho output do pipeline sinh ra trong tuong lai.
- `04_scripts/`
  Danh cho script xu ly va tu dong hoa quy trinh `CSV -> CDT -> DDF`.
- `99_archive/`
  Noi tam luu cac file da bi loai khoi workspace truoc khi xoa hoan toan.

## Ghi chu

- Khong tao them file `.cdt` hoac `.ddf` moi trong buoc tai cau truc nay.
- Mot so file du kien trong mo hinh dich chua hien dien trong workspace va chua duoc tao moi.
- Workspace co 2 lop rule:
  - `RULES.md` cho nguoi doc
  - `workspace_rules.json` cho script doc va thuc thi
