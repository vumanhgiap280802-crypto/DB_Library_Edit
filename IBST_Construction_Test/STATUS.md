# STATUS

## Workspace State

- Da archive skeleton cu vao `99_archive/legacy_workspace_20260418/`
- Da tai cau truc workspace thanh 5 nhom: `01_designbuilder_format`, `02_csv_input`, `03_output`, `04_scripts`, `99_archive`
- Da tao `README.md`, `RULES.md`, `STATUS.md`, va `workspace_rules.json` theo mo hinh cua `IBST_Materials_Test`
- Da tao `04_scripts/build_constructions_package.py` lam entry point chuan cho workspace
- Da co reference DDF that tai `01_designbuilder_format/Construction sample.DDF`
- Da trich `Constructions_exported_reference.cdt` tu `Construction sample.DDF`
- Da tao `Constructions_exported_reference_schema.json` tu file CDT vua trich
- Reference CDT hien co 20 category ids, 176 fields, va 3 records
- Da khoa bo mapping CSV construction dang `long-by-layer` dua tren file CSV that trong `02_csv_input/`
- Da co file input that: `02_csv_input/construction_input_long_distinct_from_reference.csv`
- Mode `analyse-input` da pass tren CSV hien tai, resolve duoc 11/11 material ids va 11/11 default thicknesses
- Da implement `generate-cdt` dua tren mapping CSV hien tai va seed record theo category
- Da implement `generate-ddf` de package CDT thanh DDF theo entry noi bo cua reference export
- Da sua logic package de `Constructions_generated.ddf` chua ca `Constructions.cdt` va `Materials.cdt`, khop hon voi reference DDF va import behavior that
- Da bo sung mapping `Door -> CategoryId 9` dua tren file category local cua DesignBuilder `LocalisedCategories_1.txt`.
- Da tao DDF cho `02_csv_input/construction_input_doors_openings.csv` tai `03_output/construction-input-doors-openings/Constructions_generated.ddf`.
- DDF door/opening moi co 3 construction: `D_MAIN_STEEL_0474`, `D_BEDROOM_MDF_035`, `D_WC_UPVC_024`, va package kem `Materials.cdt` chua cac material cua.
- `01_designbuilder_format/`, `02_csv_input/`, va `03_output/` da san sang cho future input/output that

## Missing Items

Nhung file va du lieu sau chua hien co trong workspace:

- Khong con thieu construction DDF da package cho cac bo data hien tai; artifacts da co trong `03_output/construction-input-long-distinct-from-reference/` va `03_output/construction-input-doors-openings/`.

## Current Script Capability

- `summary`: in ra tom tat workspace, input dang co, reference dang co/thieu, va trang thai future pipeline
- `extract-reference`: trich `Constructions.cdt` tu `Construction sample.DDF` va tao schema JSON tu file CDT vua trich
- `analyse-schema`: doc schema + CDT tham chieu, phan nhom fields, phan tich slot layers, variation, va guidance cho buoc nhap lieu
- `analyse-input`: doc CSV trong `02_csv_input/`, group construction rows, map sang model CDT muc tieu, va kiem tra kha nang resolve material ids/default thickness
- `generate-cdt`: clone seed theo category, map layer/material/thickness tu CSV, va ghi `Constructions_generated.cdt` vao mot thu muc output on dinh theo data input trong `03_output/`; chay lai cung request/cung data se replace file cu
- `generate-ddf`: sinh lai CDT cho data hien tai, chon material Id catalog nhat quan, package thanh `Constructions_generated.ddf` voi `Constructions.cdt` + `Materials.cdt`, va validate package
- `preflight`: xac nhan workspace da du bo reference `DDF + extracted CDT + schema` cho buoc mapping tiep theo

## Next Direction

- dung `generate-cdt` de sinh va review construction CDT that tu CSV mapping da khoa
- dung `generate-ddf` de tao import package dau tien va import test trong DesignBuilder
