# IBST_Construction_Test

Workspace nay duoc dung de phan tich va chuan hoa quy trinh tao construction package moi tu du lieu ben ngoai, sau do dong goi de import vao DesignBuilder.

## Muc tieu hien tai

- dong bo workspace theo mo hinh van hanh cua `IBST_Materials_Test`
- chuan bi reference/input/output/script structure cho construction workflow
- khoa lai cac rule de sau nay co the bo sung mapping `CSV -> CDT -> DDF`
- giu lai skeleton cu trong `99_archive/legacy_workspace_20260418/`

## Cau truc hien tai

- `01_designbuilder_format/`
  Chua file tham chieu export tu DesignBuilder cho Constructions.
- `02_csv_input/`
  Chua file CSV dau vao va du lieu trung gian cho construction workflow.
- `03_output/`
  Danh cho output do pipeline sinh ra trong tung lan chay.
- `04_scripts/`
  Danh cho script preflight/build cua workspace.
- `99_archive/`
  Noi luu skeleton cu va cac file bi loai khoi workspace truoc khi xoa han.

## Ghi chu

- Hien workspace da co 1 reference DDF that: `01_designbuilder_format/Construction sample.DDF`.
- Da trich duoc `Constructions_exported_reference.cdt` va `Constructions_exported_reference_schema.json` tu reference DDF hien tai.
- Da khoa bo mapping CSV construction dang `long-by-layer` trong `workspace_rules.json`.
- Script `04_scripts/build_constructions_package.py` hien ho tro `summary`, `extract-reference`, `analyse-schema`, `analyse-input`, `generate-cdt`, `generate-ddf`, va `preflight`.
- `generate-cdt` dung seed record theo `category`, map lai `Mat i / Thick i` tu CSV, va sinh `Constructions_generated.cdt` vao mot thu muc output on dinh theo ten data trong `03_output/`; neu chay lai cung request/cung data thi file cu se bi replace.
- `generate-ddf` package `Constructions_generated.cdt` thanh `Constructions_generated.ddf` voi 2 entry noi bo `Constructions.cdt` va `Materials.cdt`; `Materials.cdt` duoc lay tu mot material catalog nhat quan cover du tat ca material names dang duoc tham chieu.
- Construction reference `.cdt` duoc trich tu entry `Constructions.cdt` ben trong reference DDF.
- Khong tao thu cong file `.cdt` hoac `.ddf` moi khi chua co reference va mapping ro rang.
- Workspace co 2 lop rule:
  - `RULES.md` cho nguoi doc
  - `workspace_rules.json` cho script doc va thuc thi
