# RULES

## Scope

Workspace nay la noi phan tich va chuan hoa quy trinh import glazing vao DesignBuilder tu du lieu ben ngoai.

## Rule Source

- `RULES.md` la ban giai thich cho nguoi doc.
- `workspace_rules.json` la ban cau hinh cho may doc.
- Moi thay doi trong `RULES.md` co anh huong den hanh vi workspace phai duoc cap nhat dong thoi trong `workspace_rules.json`.
- Mot thay doi rule duoc xem la chua hoan tat neu chua cap nhat ca `RULES.md` va `workspace_rules.json`.

## Rules

- `01_designbuilder_format/` la khu vuc tham chieu, khong sua tuy tien cac file goc trong do.
- `02_csv_input/` la khu vuc dau vao de bien doi tu nguon ben ngoai.
- `03_output/` chi dung cho file duoc sinh ra boi pipeline trong tuong lai.
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
- Reference glazing DDF hien tai co 3 entry noi bo: `Glazing.cdt`, `Panes.cdt`, va `WindowGas.cdt`.
- Khi can chinh sua ben ngoai DesignBuilder, uu tien thao tac tren `.cdt`, sau do dong goi lai thanh `.ddf`.
- `.cdt` khong phai la import artifact cuoi trong workflow van hanh; `.ddf` moi la artifact cuoi dung de import vao DesignBuilder.
- Khi sinh `.ddf` moi, phai tao no bang cach zip cac `.cdt` can import roi doi duoi ve `.ddf`, khong coi `.ddf` la mot file text de sua truc tiep.
- Moi quy trinh import moi phai doi chieu voi mot `.ddf/.cdt` tham chieu da xuat tu DesignBuilder truoc khi dong goi output moi.

## Glazing

- Glazing trong DesignBuilder la component data va phai duoc doi chieu voi mot glazing package da export tu DesignBuilder.
- Glazing workflow co the lien quan den pane kinh, window gas, optical properties, solar/visible transmittance, frame/library fields, va cac field mo rong khac.
- Voi `1-Material layers`, cac slot `Mat` trong `Glazing.cdt` phai duoc hieu la tham chieu component: slot le (`Mat 1`, `Mat 3`, `Mat 5`, `Mat 7`) la Pane, slot chan (`Mat 2`, `Mat 4`, `Mat 6`) la Window gas.
- Khong ghi thang ten material/pane/gas tuy y vao `Mat`; neu khong phai numeric id DesignBuilder thi phai resolve qua catalog `Panes.cdt` hoac `WindowGas.cdt` da xac nhan.
- Chua duoc suy doan schema CSV cho glazing khi chua trich va phan tich cac CDT that trong reference DDF.
- Sau khi co reference DDF, buoc dung la trich `Glazing.cdt`, `Panes.cdt`, `WindowGas.cdt`, tao schema JSON, roi moi khoa mapping CSV -> CDT.
