# Setup Python Environment - PowerShell Script
# Usage: .\scripts\setup_python_env.ps1

param(
    [switch]$Dev = $false
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "DB_LIBRARY_EDIT - Python Environment Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check Python
Write-Host "[1/5] Checking Python..." -ForegroundColor Yellow
$pythonCmd = $null
foreach ($cmd in @("py -3", "python", "python3")) {
    try {
        $version = & $cmd --version 2>&1
        Write-Host "  Found: $cmd -> $version" -ForegroundColor Green
        $pythonCmd = $cmd
        break
    } catch {
        # Continue to next
    }
}

if ($null -eq $pythonCmd) {
    Write-Host "  ERROR: Python not found. Please install Python 3.x" -ForegroundColor Red
    exit 1
}

# Step 2: Create .venv if not exist
Write-Host "[2/5] Creating virtual environment..." -ForegroundColor Yellow
if (Test-Path ".\.venv") {
    Write-Host "  .venv already exists, skipping creation" -ForegroundColor Green
} else {
    Write-Host "  Creating .venv..." -ForegroundColor Cyan
    & $pythonCmd -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: Failed to create .venv" -ForegroundColor Red
        exit 1
    }
    Write-Host "  .venv created successfully" -ForegroundColor Green
}

# Step 3: Activate .venv
Write-Host "[3/5] Activating environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1
Write-Host "  Environment activated" -ForegroundColor Green

# Step 4: Upgrade pip, setuptools, wheel
Write-Host "[4/5] Upgrading pip, setuptools, wheel..." -ForegroundColor Yellow
python -m pip install --upgrade pip setuptools wheel -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "  WARNING: Failed to upgrade pip/setuptools/wheel" -ForegroundColor Yellow
} else {
    Write-Host "  Upgraded successfully" -ForegroundColor Green
}

# Step 5: Install requirements
Write-Host "[5/5] Installing requirements..." -ForegroundColor Yellow
if ($Dev) {
    Write-Host "  Installing production + development packages..." -ForegroundColor Cyan
    pip install -q -r requirements.txt -r requirements-dev.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: Failed to install requirements" -ForegroundColor Red
        exit 1
    }
    Write-Host "  Development packages installed" -ForegroundColor Green
} else {
    Write-Host "  Installing production packages..." -ForegroundColor Cyan
    pip install -q -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: Failed to install requirements" -ForegroundColor Red
        exit 1
    }
    Write-Host "  Production packages installed" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Setup completed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Verify environment: python scripts\smoke_test.py" -ForegroundColor White
Write-Host "  2. Add -Dev flag to install dev packages: .\scripts\setup_python_env.ps1 -Dev" -ForegroundColor White
Write-Host ""
