# IBST_Glazing_Test

Workspace nay duoc dung de phan tich va chuan hoa quy trinh tao glazing package moi tu du lieu ben ngoai, sau do dong goi de import vao DesignBuilder.

## Muc tieu hien tai

- tach rieng cong viec glazing khoi materials va constructions
- chuan bi reference/input/output/script structure cho glazing workflow
- da co reference DDF that trong `01_designbuilder_format/`
- da trich schema cho `Glazing.cdt`, `Panes.cdt`, va `WindowGas.cdt`
- chua sinh DDF moi tu CSV neu chua khoa mapping Pane/WindowGas

## Cau truc hien tai

- `01_designbuilder_format/`
  Chua file tham chieu export tu DesignBuilder cho Glazing va cac CDT/schema da trich.
- `02_csv_input/`
  Chua file CSV dau vao va du lieu trung gian cho glazing workflow.
- `03_output/`
  Danh cho output do pipeline sinh ra trong tung lan chay.
- `04_scripts/`
  Danh cho script preflight/build cua workspace.
- `99_archive/`
  Noi luu file cu hoac file bi loai khoi workspace truoc khi xoa han.

## Ghi chu

- Khong tao thu cong file `.cdt` hoac `.ddf` moi khi chua co reference va mapping ro rang.
- Voi glazing material layers, can xu ly dung tham chieu Pane va WindowGas thay vi ghi thang ten material vao `Mat`.
- Workspace co 2 lop rule:
  - `RULES.md` cho nguoi doc
  - `workspace_rules.json` cho script doc va thuc thi
