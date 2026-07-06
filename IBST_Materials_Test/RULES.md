# RULES

## Scope

Workspace nay la noi phan tich va chuan hoa quy trinh import vat lieu vao DesignBuilder tu du lieu ben ngoai.

## Rule Source

- `RULES.md` la ban giai thich cho nguoi doc.
- `workspace_rules.json` la ban cau hinh cho may doc.
- Moi thay doi trong `RULES.md` co anh huong den hanh vi workspace phai duoc cap nhat dong thoi trong `workspace_rules.json`.
- Mot thay doi rule duoc xem la chua hoan tat neu chua cap nhat ca `RULES.md` va `workspace_rules.json`.

## Rules

- `01_designbuilder_format/` la khu vuc tham chieu, khong sua tuy tien cac file goc trong do.
- `02_csv_input/` la khu vuc dau vao de bien doi tu nguon ben ngoai.
- Script quet tat ca file `.csv` dang hoat dong trong `02_csv_input/`, khong khoa cung vao 2 ten file co dinh.
- File `.csv` bat dau bang `_` duoc xem la file phu/tam va bi bo qua trong qua trinh tu dong hoa.
- Phan loai `Detailed` va `NoMass` duoc xac dinh bang tap cot bat buoc va gia tri cot `Type`, khong dua vao ten file.
- Thu tu xu ly input la tat ca file `Detailed` theo thu tu ten file tang dan, sau do den tat ca file `NoMass` theo thu tu ten file tang dan.
- `03_output/` chi dung cho file duoc sinh ra boi pipeline trong tuong lai.
- Moi lan chay script de sinh output `.cdt` hoac `.ddf`, pipeline phai tu dong tao mot thu muc con moi trong `03_output/` de chua ket qua cua rieng lan chay do.
- Ten thu muc output phai duoc dan xuat tu ten data input duoc chay; neu can tranh trung giua nhieu lan chay cung input thi duoc phep them timestamp o cuoi ten thu muc.
- Khong ghi de output cua lan chay moi len output cua lan chay truoc trong cung root `03_output/`.
- `04_scripts/` la noi luu script xu ly va tu dong hoa cua workspace.
- `99_archive/` la noi tam luu cac file da bi loai khoi workspace truoc khi xoa hoan toan.
- Mac dinh moi thao tac la sua chua/cap nhat tren file hien co.
- Chi tao file moi khi co lenh tao ro rang hoac khi pipeline sinh output duoc xac dinh truoc.
- Khong tao thu cong file `.cdt` / `.ddf` moi neu chua co buoc sinh file ro rang.
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
- Khi dong goi `Materials_generated.ddf`, entry `.cdt` ben trong package phai dung ten noi bo theo reference DDF export tu DesignBuilder, hien tai la `Materials.cdt`.
- `Materials_generated.cdt` la artifact trung gian de debug/sua; khi dong goi thanh `.ddf`, script phai dua noi dung file nay vao entry `Materials.cdt` ben trong package.
- File CSV xuat tu DesignBuilder chi phu hop de xem/phan tich trong spreadsheet; theo tai lieu DesignBuilder, CSV nay khong duoc doc nguoc tro lai de import.
- Moi quy trinh import moi phai doi chieu voi mot `.ddf/.cdt` tham chieu da xuat tu DesignBuilder truoc khi dong goi output moi.

## Materials

- Materials trong DesignBuilder la component data va co the duoc tham chieu boi cac component khac nhu Constructions.
- Mot material co the chua cac nhom du lieu sau:
  - General thermo-physical va Moisture Transfer
  - Surface Properties
  - Green Roof
  - Embodied Carbon
  - Phase Change
- Khi phan tich hoac sinh Materials moi tu ben ngoai, phai doi chieu voi mot `.ddf/.cdt` Materials tham chieu da duoc export tu DesignBuilder.
- Neu can import Materials moi vao model, co the import `.ddf` khi model dang mo; neu can dua Materials moi vao component library dung cho cac model sau, phai import `.ddf` vao library khi khong mo model.
- Bat ky component nao duoc them khi model dang mo se tro thanh Model component, khong tu dong tro thanh Library component.
- Neu muon Materials moi co san cho cac model moi, phai export/import theo luong library data cua DesignBuilder.
- Khong xem system materials la doi tuong sua truc tiep; neu can chinh sua mot system material, phai clone/tao ban user-defined tuong duong roi moi sua.
- Khi sinh Materials tu ben ngoai, uu tien tao user-defined materials ro rang, de tranh nham lan voi system data cua DesignBuilder.

## Materials Field Rules

- `CSV discovery`
  - Script doc moi file `.csv` hop le trong `02_csv_input/`.
  - File `Detailed` phai co cac cot: `Name`, `Type`, `Roughness`, `DefaultThickness_m`, `Conductivity_W_mK`, `Density_kg_m3`, `SpecificHeat_J_kgK`, `ThermalAbsorptance`, `SolarAbsorptance`, `VisibleAbsorptance`, `ForceThickness`, `Notes`.
  - File `NoMass` phai co cac cot: `Name`, `Type`, `Roughness`, `ThermalResistance_m2K_W`, `ThermalAbsorptance`, `SolarAbsorptance`, `VisibleAbsorptance`, `Notes`.
  - Moi dong trong file `Detailed` phai co `Type = Detailed`.
  - Moi dong trong file `NoMass` phai co `Type = NoMass`.
- `Name`
  - `Name` trong CSV la nguon chinh de sinh `Name` trong CDT.
  - Truoc khi dung, phai trim khoang trang dau/cuoi.
  - Khong duoc chua ky tu `#` vi day la delimiter cua CDT.
  - Khong tu dong cat ngan, doi ten, hay sua ten de khop voi sample cu bi rut gon.
  - Sau khi chuan hoa, moi `Name` phai la duy nhat trong toan bo CSV input.
  - Neu sample CDT hien co chua ten bi rut gon thi xem do la legacy inconsistency, khong xem la rule dung de noi theo.
- `Roughness`
  - CSV chi duoc dung 6 gia tri chuan: `VeryRough`, `Rough`, `MediumRough`, `MediumSmooth`, `Smooth`, `VerySmooth`.
  - Khi ghi vao CDT, phai map theo nhan cua DesignBuilder:
    - `VeryRough -> 1-Very rough`
    - `Rough -> 2-Rough`
    - `MediumRough -> 3-Medium rough`
    - `MediumSmooth -> 4-Medium smooth`
    - `Smooth -> 5-Smooth`
    - `VerySmooth -> 6-Very smooth`
- `Description`
  - `Description` trong CDT duoc nap tu cot `Notes` cua CSV.
  - Truoc khi ghi vao CDT, phai thay `#` bang khoang trang, trim dau/cuoi, va gom khoang trang lien tiep.
  - Khong de delimiter cua CDT di thang vao noi dung field text.
- `ForceThickness`
  - Ap dung cho material `Detailed`: `Yes`, `True`, `1` duoc quy doi thanh `1`; `No`, `False`, `0`, rong duoc quy doi thanh `0`.
  - Voi `NoMass`, `ForceThickness` mac dinh la `0`.
  - Neu `ForceThickness = 1` thi `DefaultThickness_m` phai co gia tri duong hop le.
  - Rule nay duoc uu tien hon sample CDT cu neu sample cu dang de `0` hang loat.
- `Id`
  - `Id` la field duoc sinh boi pipeline, khong lay truc tiep tu CSV.
  - Quy tac sinh `Id` la lay `max(Id)` tu reference hop le roi tang tuan tu them `+1`.
  - Thu tu cap `Id` cua pipeline la theo thu tu dong trong `materials_detailed.csv`, sau do den `materials_nomass.csv`.
  - Khong tai su dung `Id` da cap o package khac.

## Materials Seed Templates

- File tham chieu de lay seed record la `01_designbuilder_format/Materials_exported_reference.cdt`, duoc trich truc tiep tu `Materials.DDF` export tu DesignBuilder.
- `Detailed seed` duoc co dinh la record `IBST_SEED_DETAILED_REAL`.
- `NoMass seed` duoc co dinh la record `IBST_SEED_NOMASS_REAL`.
- Seed record chi duoc dung cho cac field chua duoc CSV va rules dieu khien.
- Moi field da duoc map boi CSV/rule phai overwrite seed, khong duoc giu gia tri legacy tu seed neu da co rule ro rang.
- Uu tien seed duoc export truc tiep tu DesignBuilder hon moi sample QA/generator cu.
