# DB_LIBRARY_EDIT

`DB_LIBRARY_EDIT` là workspace dùng để quản lý, sinh và kiểm tra dữ liệu thư viện
DesignBuilder. Project hiện tại tập trung vào việc chuyển dữ liệu đầu vào dạng
CSV thành các bảng `.cdt` tương thích với DesignBuilder, sau đó đóng gói thành
file `.ddf` để import vào DesignBuilder.

Workspace này không chỉ là nơi lưu file DesignBuilder rời rạc. Nó được tổ chức
như một pipeline dữ liệu có kiểm soát.

## Mục Đích Hiện Tại

Mục đích chính của project là quản lý dữ liệu thư viện DesignBuilder theo một
quy trình có thể lặp lại:

```text
Reference DDF/CDT -> CSV input -> generated CDT -> generated DDF -> import test
```

Hiểu đơn giản:

- `.csv` là file đầu vào có thể chỉnh sửa.
- `.cdt` là bảng dữ liệu text nằm bên trong gói DesignBuilder.
- `.ddf` là gói import/export cuối cùng của DesignBuilder.

Các nhóm dữ liệu đang được xử lý:

- Materials
- Constructions
- Glazing
- Panes
- Window gas

Cách làm hiện tại có thể mở rộng sang các component library và template library
khác của DesignBuilder, với điều kiện phải có file `.ddf` tham chiếu thật được
export từ DesignBuilder trước khi phân tích schema và viết generator.

## Cấu Trúc Workspace

```text
DB_LIBRARY_EDIT/
|-- 00_admin/
|   |-- WORKSPACE_RULES.md
|   |-- WORKSPACE_RULES_LOCAL.md
|   |-- WORKSPACE_FLOW.md
|   |-- CHANGE_POLICY.md
|   |-- NAMING_CONVENTIONS.md
|   `-- PYTHON_ENVIRONMENT.md
|-- scripts/
|   |-- smoke_test.py
|   |-- setup_python_env.ps1
|   `-- setup_python_env.sh
|-- IBST_Materials_Library/
|-- IBST_Materials_Test/
|-- IBST_Glazing_Test/
|-- IBST_Construction_Test/
`-- 04_build_candidates/
```

## Các Workspace Chính

| Workspace | Vai trò | Trạng thái hiện tại |
| --- | --- | --- |
| `IBST_Materials_Library` | Workspace chính thức cho dữ liệu Materials | Có tài liệu quản trị và lịch sử phân tích |
| `IBST_Materials_Test` | Workspace thử nghiệm sinh Materials | Có CSV đầu vào, reference CDT/DDF, script generator và output đã sinh |
| `IBST_Glazing_Test` | Workspace thử nghiệm sinh Glazing | Hỗ trợ Glazing, Panes và WindowGas |
| `IBST_Construction_Test` | Workspace thử nghiệm sinh Constructions | Hỗ trợ CSV dạng long-by-layer và đóng gói DDF |
| `04_build_candidates` | Khu vực chứa build candidate tổng hợp | Có candidate gộp Materials, Glazing và Constructions |

## Chức Năng Hiện Có

### Materials

Workspace:

```text
IBST_Materials_Test
```

Script chính:

```powershell
cd IBST_Materials_Test\04_scripts
..\..\.venv\Scripts\python.exe .\build_materials_package.py --mode preflight
```

Các mode đang hỗ trợ:

- `preflight`
- `analyse-mapping`
- `generate-cdt`
- `generate-ddf`

Ghi chú hiện tại: `preflight` đang pass. `analyse-mapping` đang báo các lệch
đã biết giữa dữ liệu mẫu cũ và bộ rule hiện tại, gồm trùng tên material trong
CSV đang active, khác biệt về roughness, description, force thickness và thứ tự
ID. Vì vậy không nên xem output Materials là final nếu chưa xử lý các cảnh báo
này.

### Glazing

Workspace:

```text
IBST_Glazing_Test
```

Script chính:

```powershell
cd IBST_Glazing_Test\04_scripts
..\..\.venv\Scripts\python.exe .\build_glazing_package.py --input-file glazing_input_doors_simple_for_designbuilder.csv
```

Workflow Glazing hiện hỗ trợ:

- `Glazing.cdt`
- `Panes.cdt`
- `WindowGas.cdt`
- Glazing dạng simple
- Glazing dạng material layers có tham chiếu Pane và WindowGas

### Constructions

Workspace:

```text
IBST_Construction_Test
```

Script chính:

```powershell
cd IBST_Construction_Test\04_scripts
..\..\.venv\Scripts\python.exe .\build_constructions_package.py --mode preflight
```

Các mode đang hỗ trợ:

- `summary`
- `extract-reference`
- `analyse-schema`
- `analyse-input`
- `generate-cdt`
- `generate-ddf`
- `preflight`

Workflow Construction dùng mô hình CSV dạng long-by-layer:

```text
1 dòng CSV = 1 lớp vật liệu trong construction
```

Generator sẽ gom các dòng thành từng construction, resolve material ID và default
thickness, tạo `Constructions_generated.cdt`, rồi đóng gói thành
`Constructions_generated.ddf` cùng với `Materials.cdt` bắt buộc.

## Python Environment

Project dùng một virtual environment chung ở root:

```text
.venv/
```

Dependencies chạy production được khai báo tại:

```text
requirements.txt
```

Dependencies cho development được khai báo tại:

```text
requirements-dev.txt
```

Setup trên Windows PowerShell:

```powershell
.\scripts\setup_python_env.ps1
```

Setup kèm công cụ development:

```powershell
.\scripts\setup_python_env.ps1 -Dev
```

Smoke test:

```powershell
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe .\scripts\smoke_test.py
```

Biến `PYTHONIOENCODING` giúp tránh lỗi encoding trên Windows console khi script
in ký hiệu trạng thái.

## Mô Hình Dữ Liệu DesignBuilder

Project hiện dùng mô hình làm việc sau:

- DesignBuilder import/export components và templates bằng gói `.ddf`.
- Một gói `.ddf` có thể chứa một hoặc nhiều bảng `.cdt`.
- Dữ liệu mới nên được sinh từ CSV và schema rule, sau đó ghi ra `.cdt`, rồi
  đóng gói thành `.ddf`.
- Các file `.ddf` và `.cdt` tham chiếu phải được xem như read-only.
- File `.ddf` sinh ra cần được kiểm tra bằng import test trong DesignBuilder.

Các cấu trúc đã quan sát trong workspace:

| Loại package | Entry CDT bên trong |
| --- | --- |
| Materials | `Materials.cdt` |
| Glazing simple | `Glazing.cdt` |
| Glazing material layers | `Glazing.cdt`, `Panes.cdt`, `WindowGas.cdt` |
| Constructions | `Constructions.cdt`, `Materials.cdt` |
| Candidate tổng hợp | `Constructions.cdt`, `Glazing.cdt`, `Materials.cdt` |

## Hướng Mở Rộng

Workspace này có thể mở rộng vượt ra ngoài Materials, Glazing và Constructions.
Nguyên tắc đề xuất: không tự đoán schema. Trước tiên cần export một file `.ddf`
thật từ DesignBuilder, trích các file `.cdt`, tạo schema, rồi mới xây mapping
CSV và generator.

Các hướng nên ưu tiên trước:

- `Schedules`
- `Activity templates`
- `Construction templates`
- `Glazing templates`
- `Profiles`
- `Holidays`
- `Tariffs`
- `Summary Output`

Các hướng phức tạp hơn:

- `HVAC templates`
- `Detailed HVAC Template`
- `DHW Templates`
- `Boiler`
- `Chillers`
- `Cooling System`
- `HVAC Systems`
- `Curves`
- `Generators`
- `Photovoltaic Generator`
- `Inverters`
- `Storage`

Các hướng cần thận trọng cao:

- `Scripts`
- `FMU Program`
- `Electronic Sensor`
- `Hourly weather`
- các resource phụ thuộc file ngoài không nằm hoàn toàn trong `.ddf`

Gợi ý tên workspace test trong tương lai:

```text
IBST_Schedules_Test/
IBST_ActivityTemplates_Test/
IBST_HVAC_Templates_Test/
IBST_SummaryOutput_Test/
IBST_Scripts_Test/
```

Mỗi workspace test mới nên đi theo pattern hiện tại:

```text
01_designbuilder_format/
02_csv_input/
03_output/
04_scripts/
99_archive/
```

## Quy Tắc An Toàn

Các quy tắc quan trọng:

- Không sửa trực tiếp file `.ddf` hoặc `.cdt` tham chiếu.
- Không đổi tên thủ công artifact của DesignBuilder nếu workflow không yêu cầu.
- Không release từ test workspace.
- Xem `IBST_Materials_Library` là workspace chính thức.
- Dùng các test workspace để thử nghiệm và import validation.
- Ưu tiên sửa trực tiếp file tài liệu/script hiện có, không tạo bản `_new`,
  `_fixed`, `_v2` song song.
- Với artifact do pipeline sinh ra, chỉ dùng đúng output location đã định nghĩa.
- Ghi nhận thay đổi lớn trong report hoặc status file.

Xem thêm:

- `AGENTS.md`
- `00_admin/WORKSPACE_RULES.md`
- `00_admin/WORKSPACE_RULES_LOCAL.md`
- `00_admin/CHANGE_POLICY.md`

## Chuẩn Bị Upload Lên GitHub

Trước khi upload lên GitHub:

1. Kiểm tra các file `.ddf`, `.cdt`, `.csv`, `.pkl` có chứa dữ liệu riêng tư,
   dữ liệu có bản quyền hoặc dữ liệu nhạy cảm của project không.
2. Đảm bảo không commit `.env` hoặc credential local.
3. Không commit `.venv/`, `__pycache__/`, `.pytest_cache/` hoặc file backup.
4. Kiểm tra `.gitignore` trước commit đầu tiên.
5. Nếu repository để public, cần xác nhận các file mẫu có nguồn từ
   DesignBuilder được phép chia sẻ.

Các lệnh kiểm tra nên chạy trước:

```powershell
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe .\scripts\smoke_test.py

cd IBST_Materials_Test\04_scripts
..\..\.venv\Scripts\python.exe .\build_materials_package.py --mode preflight

cd ..\..\IBST_Construction_Test\04_scripts
..\..\.venv\Scripts\python.exe .\build_constructions_package.py --mode preflight
```

## Tài Liệu DesignBuilder Tham Khảo

- [DesignBuilder Help - Export Components/Templates](https://designbuilder.co.uk/helpv7.0/Content/Export_Components_Templates1.htm)
- [DesignBuilder Help - Import Components/Templates](https://designbuilder.co.uk/helpv7.0/Content/Import_Components.htm)
- [DesignBuilder Help - Importing Custom Templates and Components](https://designbuilder.co.uk/helpv7.0/Content/ImportingCustomTemplatesAndComponents.htm)
- [DesignBuilder Help - Glazing layer data](https://designbuilder.co.uk/helpv7.0/Content/_Glazing_layer_data.htm)

## Trạng Thái Project

Trạng thái hiện tại:

- Root đã có bộ quy tắc quản trị và công cụ Python chung.
- Đã có workflow test cho Materials, Glazing và Constructions.
- Construction preflight và input analysis đang pass.
- Materials preflight đang pass, nhưng mapping analysis báo các lệch đã biết
  giữa rule hiện tại và sample/dữ liệu cũ.
- Việc mở rộng sang library type mới là khả thi nếu mỗi loại mới bắt đầu từ
  một reference export thật từ DesignBuilder.

## License

Project hiện chưa khai báo license. Nên thêm license trước khi public repository
nếu muốn người khác được phép tái sử dụng code hoặc dữ liệu.
