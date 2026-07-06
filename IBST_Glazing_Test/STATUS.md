# STATUS

## Workspace State

- Da tao workspace `IBST_Glazing_Test` cung cap voi `IBST_Materials_Test` va `IBST_Construction_Test`.
- Da tao cau truc 5 nhom: `01_designbuilder_format`, `02_csv_input`, `03_output`, `04_scripts`, `99_archive`.
- Da tao `README.md`, `RULES.md`, `STATUS.md`, va `workspace_rules.json`.
- Da co reference DDF that: `01_designbuilder_format/Sample_Glazing.DDF`.
- Sample moi hien co 3 entry noi bo: `Glazing.cdt`, `Panes.cdt`, va `WindowGas.cdt`.
- Da trich lai `Glazing_exported_reference.cdt` tu entry `Glazing.cdt`.
- Da trich moi `Panes_exported_reference.cdt` tu entry `Panes.cdt`.
- Da trich moi `WindowGas_exported_reference.cdt` tu entry `WindowGas.cdt`.
- Da tao lai 3 schema JSON tu cac CDT vua trich:
  - `Glazing_exported_reference_schema.json`: 135 fields, 4 records.
  - `Panes_exported_reference_schema.json`: 27 fields, 1 record.
  - `WindowGas_exported_reference_schema.json`: 29 fields, 1 record.
- Da tao schema CSV dau vao cho 3 bang glazing lien quan:
  - `02_csv_input/schema/glazing_input_schema.csv`
  - `02_csv_input/schema/panes_input_schema.csv`
  - `02_csv_input/schema/window_gas_input_schema.csv`
- Da tao folder con `02_csv_input/schema/` de tach schema CSV khoi CSV du lieu dau vao.
- `Glazing.cdt` reference dung encoding `windows-1252`; `Panes.cdt` va `WindowGas.cdt` co the doc duoc bang `utf-8-sig`.
- Sample moi co ca `1-Material layers` va `2-Simple`; generator hien tai da ho tro ca 2 workflow nay o muc input hien co.
- Da cap nhat `04_scripts/build_glazing_package.py` de dong goi them `Panes.cdt` va `WindowGas.cdt` khi sau nay tao DDF.
- Da cap nhat generator de khong ghi thang ten pane/gas khong resolve duoc vao cac cot `Mat`; neu CSV dung ten chua co trong catalog reference thi script se bao loi truoc khi tao DDF.
- Da cap nhat generator de co the doc `02_csv_input/panes_input_from_glass_for_designbuilder.csv`, sinh `Panes_generated.cdt`, va resolve `mat_1_ref` trong glazing CSV sang pane id moi.
- Output moi nhat: `03_output/glazing_input_doors_for_designbuilder_20260603_143328/Glazing_generated.ddf`.
- Output moi nhat co 3 entry noi bo: `Glazing.cdt`, `Panes.cdt`, va `WindowGas.cdt`.
- Trong output moi, `Panes.cdt` duoc sinh tu pane CSV; `WindowGas.cdt` van lay tu reference vi 2 glazing hien tai deu la 1 lop va khong can gas layer.
- Da cap nhat generator de tao DDF cho `DefinitionMethod = 2-Simple` tu `02_csv_input/glazing_input_doors_simple_for_designbuilder.csv`.
- Output Simple moi nhat: `03_output/glazing_input_doors_simple_for_designbuilder_20260603_145055/Glazing_generated.ddf`.
- Output Simple chi co entry noi bo `Glazing.cdt` vi workflow `2-Simple` dung U-value, SHGC, va VT tong the, khong can Pane/WindowGas.

## Important Finding

- Loi import truoc do co kha nang cao den tu viec `Mat 1..7` bi ghi bang chuoi ten material/pane tu CSV, trong khi DesignBuilder can tham chieu Pane/WindowGas hop le.
- Trong sample moi, cac slot `Mat` cua `Glazing.cdt` van la gia tri numeric nho nhu `1`, `2`, `3`; cac record custom trong `Panes.cdt` va `WindowGas.cdt` co `Id = 10000`.
- Vi vay chua nen tu dong suy dien mapping ten thuong mai nhu `GLASS_TEMPERED_010` sang ID DesignBuilder neu chua co catalog Pane/WindowGas duoc xac nhan.

## Missing Items

Nhung phan sau van chua duoc khoa:

- Catalog WindowGas day du cho cac glazing nhieu lop neu sau nay co gas layer.
- Quy tac mapping ten trong CSV sang numeric id DesignBuilder cho WindowGas.

## Next Direction

- Neu tiep tuc tao DDF tu CSV hien co, can doi `mat_*_ref` sang numeric id hop le hoac dung ten co that trong `Panes_exported_reference.cdt` / `WindowGas_exported_reference.cdt`.
- Nen lay them sample DesignBuilder co glazing thuc su tham chieu den custom Pane va custom WindowGas de xac nhan cach ID duoc ghi trong `Mat 1..7`.
- Sau khi co catalog/mapping hop le, chay lai generator de tao DDF moi va import-test trong DesignBuilder.
