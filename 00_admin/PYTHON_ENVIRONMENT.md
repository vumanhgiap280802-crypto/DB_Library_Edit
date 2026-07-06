# DB_LIBRARY_EDIT - Python environment

Cập nhật: 2026-07-06

## Mục đích

Workspace dùng một Python virtual environment chung tại root để chạy các script hỗ trợ kiểm tra, setup và xử lý dữ liệu.

```text
DB_LIBRARY_EDIT/
|-- .venv/
|-- requirements.txt
|-- requirements-dev.txt
`-- scripts/
```

## File liên quan

| Thành phần | Vị trí | Vai trò |
| --- | --- | --- |
| Virtual environment | `.venv/` | Môi trường Python local |
| Production dependencies | `requirements.txt` | Package cần cho script chính |
| Development dependencies | `requirements-dev.txt` | Package kiểm thử/lint/format |
| Setup PowerShell | `scripts/setup_python_env.ps1` | Tạo/cài môi trường trên Windows |
| Setup Bash | `scripts/setup_python_env.sh` | Tạo/cài môi trường trên Linux/Mac |
| Smoke test | `scripts/smoke_test.py` | Kiểm tra nhanh môi trường |

## Cài đặt lần đầu

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

Linux/Mac:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

## Cài cả package phát triển

```powershell
pip install -r requirements.txt -r requirements-dev.txt
```

Hoặc dùng script có sẵn:

```powershell
.\scripts\setup_python_env.ps1
```

```bash
bash scripts/setup_python_env.sh
```

## Kiểm tra môi trường

```powershell
$env:PYTHONIOENCODING='utf-8'
python .\scripts\smoke_test.py
```

Smoke test hiện kiểm tra:

- Python version.
- Các package bắt buộc.
- Một số file cấu hình/tài liệu quản trị ở root.

Nếu smoke test báo thiếu package, cài lại bằng:

```powershell
pip install -r requirements.txt
```

Nếu Windows báo lỗi `UnicodeEncodeError` khi in ký hiệu kiểm tra, đặt encoding trước khi chạy:

```powershell
$env:PYTHONIOENCODING='utf-8'
python .\scripts\smoke_test.py
```

## Package chính

`requirements.txt` hiện phục vụ các tác vụ đọc/ghi dữ liệu phổ biến:

- `pandas`
- `openpyxl`
- `chardet`
- `python-dotenv`

`requirements-dev.txt` phục vụ kiểm thử và phát triển:

- `pytest`
- `black`
- `ruff`

## Quy tắc bảo trì

- Không commit `.venv` lên GitHub.
- Khi thêm package mới, cập nhật `requirements.txt` hoặc `requirements-dev.txt`.
- Không dùng nhiều virtual environment rải rác trong các workspace con nếu không có lý do rõ.
- Script dùng chung đặt trong `scripts/`; script rất riêng cho một workspace có thể đặt trong workspace đó nếu cần.

## Lệnh nhanh

| Nhu cầu | Lệnh |
| --- | --- |
| Activate Windows | `.\.venv\Scripts\Activate.ps1` |
| Activate CMD | `.venv\Scripts\activate.bat` |
| Activate Linux/Mac | `source .venv/bin/activate` |
| Cài package | `pip install -r requirements.txt` |
| Chạy smoke test | `python .\scripts\smoke_test.py` |
| Xem package | `pip list` |

## Lưu ý cho GitHub

Trước khi upload lên GitHub, nên kiểm tra `.gitignore` đã loại trừ:

```text
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
*.bak_*
```
