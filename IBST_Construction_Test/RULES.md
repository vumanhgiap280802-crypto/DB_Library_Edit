# RULES

## Scope

Workspace nay la noi phan tich va chuan hoa quy trinh import constructions vao DesignBuilder tu du lieu ben ngoai.

## Rule Source

- `RULES.md` la ban giai thich cho nguoi doc.
- `workspace_rules.json` la ban cau hinh cho may doc.
- Moi thay doi trong `RULES.md` co anh huong den hanh vi workspace phai duoc cap nhat dong thoi trong `workspace_rules.json`.
- Mot thay doi rule duoc xem la chua hoan tat neu chua cap nhat ca `RULES.md` va `workspace_rules.json`.

## Rules

- `01_designbuilder_format/` la khu vuc tham chieu, khong sua tuy tien cac file goc trong do.
- `02_csv_input/` la khu vuc dau vao de bien doi tu nguon ben ngoai.
- Script quet tat ca file `.csv` dang hoat dong trong `02_csv_input/`, khong khoa cung vao ten file co dinh.
- File `.csv` bat dau bang `_` duoc xem la file phu/tam va bi bo qua trong qua trinh tu dong hoa.
- `03_output/` chi dung cho file duoc sinh ra boi pipeline trong tuong lai.
- Thu muc output phai duoc dan xuat on dinh tu ten data input dang chay.
- Neu la cung request voi cung data input, pipeline phai reuse lai dung thu muc output do va replace artifact cu trong thu muc ay.
- Chi tao thu muc output moi khi data input thay doi hoac bo artifact muc tieu thay doi theo mot pipeline khac.
- `04_scripts/` la noi luu script xu ly va tu dong hoa cua workspace.
- `99_archive/` la noi tam luu cac file da bi loai khoi workspace truoc khi xoa hoan toan.
- Mac dinh moi thao tac la sua chua/cap nhat tren file hien co.
- Chi tao file moi khi co lenh tao ro rang hoac khi pipeline sinh output duoc xac dinh truoc.
- Khong tao thu cong file `.cdt` / `.ddf` moi neu chua co reference, mapping, va buoc sinh file ro rang.
- CSV khong duoc xem la import artifact cuoi; artifact import chinh la `.ddf`, voi noi dung cot loi nam trong `.cdt`.
- Neu mot file khong con phu hop voi workspace, uu tien chuyen vao `99_archive/` truoc khi xem xet xoa han.

## DDF va CDT

- `.ddf` la file package ma DesignBuilder su dung de export va import component/template/library data.
- DesignBuilder doc truc tiep `.ddf` khi import vao model hoac vao library.
- `.ddf` co the duoc doi duoi thanh `.zip` de mo va lay ra cac file `.cdt` ben trong.
- `.cdt` la file du lieu text ben trong goi `.ddf`; moi dong du lieu duoc tach field bang ky tu `#`.
- Moi `.cdt` thuong gom:
  - 1 dong category ids
  - 1 dong header mo ta y nghia cac cot
  - cac dong record du lieu
- Khi can chinh sua ben ngoai DesignBuilder, uu tien thao tac tren `.cdt`, sau do dong goi lai thanh `.ddf`.
- `.cdt` khong phai la import artifact cuoi trong workflow van hanh; `.ddf` moi la artifact cuoi dung de import vao DesignBuilder.
- Khi sinh `.ddf` moi, phai tao no bang cach zip cac `.cdt` can import roi doi duoi ve `.ddf`, khong coi `.ddf` la mot file text de sua truc tiep.
- Khi dong goi `Constructions_generated.ddf`, entry `.cdt` ben trong package phai dung ten noi bo theo reference DDF export tu DesignBuilder, hien tai la `Constructions.cdt`.
- `Constructions_generated.ddf` phai dong goi kem `Materials.cdt` theo reference package structure, khong chi `Constructions.cdt`.
- `Constructions_generated.cdt` la artifact trung gian de debug/sua; khi dong goi thanh `.ddf`, script phai dua noi dung file nay vao entry `Constructions.cdt` ben trong package.
- Reference construction DDF hien tai cua workspace la `Construction sample.DDF`; tu file nay phai trich `Constructions.cdt` thanh `Constructions_exported_reference.cdt` va tao `Constructions_exported_reference_schema.json`.
- File CSV xuat tu DesignBuilder chi phu hop de xem/phan tich trong spreadsheet; theo tai lieu DesignBuilder, CSV nay khong duoc doc nguoc tro lai de import.
- Moi quy trinh import moi phai doi chieu voi mot `.ddf/.cdt` tham chieu da xuat tu DesignBuilder truoc khi dong goi output moi.

## Constructions

- Constructions trong DesignBuilder la component data va phai duoc doi chieu voi mot construction package da export tu DesignBuilder.
- Construction moi phai duoc xay dung tren field structure va thu tu layer cua reference export, khong suy doan tu markdown note hoac ten file.
- Construction workflow co the phu thuoc vao reference den materials; truoc khi build phai xac dinh ro material names hoac keys se duoc dung trong moi truong import.
- Sau khi khoa xong mapping CSV -> CDT va chot buoc dong goi, script duoc phep ho tro `analyse-input`, `generate-cdt`, va `generate-ddf`.
- Neu can import Constructions moi vao model hoac library, phai uu tien kiem tra reference export that truoc khi sinh build candidate moi.

## Future Mapping Direction

- CSV discovery van theo nguyen tac scan moi file `.csv` hop le trong `02_csv_input/`.
- CSV construction hien tai duoc khoa theo dang `long-by-layer`: 1 dong = 1 layer, group theo `construction_code + construction_name + category`, sort theo `layer_order`.
- Mapping CSV -> CDT hien tai:
  - `construction_name -> Name`
  - `category -> CategoryId` qua bang map text:
    - `External Wall -> 1`
    - `Internal Partition -> 2`
    - `Ground Floor -> 12`
    - `Door -> 9`
  - `layer_order -> slot index i` cho `Mat i` va `Thick i`
  - `material_name -> logical material reference`, sau do resolve thanh material `Id`
  - `thickness_override_m -> Thick i` neu co; neu rong thi lay default thickness tu material source theo thu tu uu tien da khai bao trong `workspace_rules.json`
  - `notes -> Description` theo note dau tien khong rong trong moi group
  - `count(rows in group) -> NumberLayers`
  - `sum(Thick i active) -> Thickness`
- `construction_code` hien duoc dung de group/diagnostic, khong map truc tiep vao field CDT neu `construction_name` da la ten dich.
- Seed record cho tung category hien tai:
  - `External Wall -> IBST_SA_EXTWALL_BRICK_EPS50`
  - `Internal Partition -> IBST_SB_PART_FC_REFL_MW_GYP`
  - `Ground Floor -> IBST_SC_GROUNDFLOOR_XPS_CONC_TILE`
  - `Door -> IBST_SA_EXTWALL_BRICK_EPS50` tam thoi, vi reference hien tai chua co Door seed rieng; generator van reset layer va nap lai material/thickness theo CSV.
- `generate-cdt` hien tai phai:
  - clone record seed theo `category`
  - reset toan bo slot `Mat i / Thick i / BMat i / PercBridge i / Bridged i`
  - nap lai layer active tu CSV da resolve
  - tinh `NumberLayers` va `Thickness` tu du lieu layer
  - ghi `Constructions_generated.cdt` vao thu muc output on dinh cua bo CSV dang chay trong `03_output/`, va replace file cu neu la cung request/cung data
- `generate-ddf` hien tai phai:
  - dam bao `Constructions_generated.cdt` da duoc sinh lai tu data input hien tai
  - chon 1 material Id catalog nhat quan cover du tat ca material names dang duoc construction tham chieu
  - package file nay thanh `Constructions_generated.ddf`
  - dung entry noi bo `Constructions.cdt` va `Materials.cdt` theo reference DDF
  - package `Materials.cdt` tu cung material catalog da duoc dung de resolve `Mat i`
  - validate lai package de dam bao noi dung cac entry ben trong trung khop voi du lieu vua sinh
- Cac field thermal/surface/library khong duoc map truc tiep tu CSV hien tai se tam thoi giu theo seed record cho tung category cho den khi co rule tinh toan/import-test ro rang.
- Material `Id` phai duoc resolve tu material catalogs uu tien da khai bao; neu khong resolve duoc thi script phai bao fail ro rang, khong duoc tu dat `Id`.
