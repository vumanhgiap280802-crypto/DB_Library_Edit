#!/usr/bin/env python
"""
Smoke Test - Verify DB_LIBRARY_EDIT Python Environment

This script checks:
  - Python version and executable path
  - Required packages (pandas, openpyxl, chardet, python-dotenv)
  - Overall environment readiness

Usage:
  python scripts/smoke_test.py
"""

import sys
import os
from pathlib import Path


def print_header(text):
    """Print formatted header"""
    print(f"\n{'='*50}")
    print(f"  {text}")
    print(f"{'='*50}")


def check_python_version():
    """Check Python version"""
    print(f"Python Version: {sys.version}")
    print(f"Executable: {sys.executable}")
    
    # Check minimum version
    if sys.version_info < (3, 7):
        print("  ⚠ WARNING: Python 3.7+ recommended")
        return False
    return True


def check_imports():
    """Check if required packages can be imported"""
    required_packages = {
        'pandas': 'Data manipulation',
        'openpyxl': 'Excel support',
        'chardet': 'Character encoding detection',
        'dotenv': 'Environment variables (.env)',
    }
    
    optional_packages = {
        'pytest': 'Testing framework (dev)',
        'black': 'Code formatter (dev)',
        'ruff': 'Linter (dev)',
    }
    
    print("\n[Required Packages]")
    required_ok = True
    for pkg, description in required_packages.items():
        try:
            __import__(pkg)
            print(f"  ✓ {pkg:<15} - {description}")
        except ImportError:
            print(f"  ✗ {pkg:<15} - {description} (MISSING)")
            required_ok = False
    
    print("\n[Optional Packages (Dev)]")
    optional_ok = True
    for pkg, description in optional_packages.items():
        try:
            __import__(pkg)
            print(f"  ✓ {pkg:<15} - {description}")
        except ImportError:
            print(f"  ✗ {pkg:<15} - {description} (not installed)")
            optional_ok = False
    
    return required_ok, optional_ok


def check_environment_files():
    """Check if environment files exist"""
    print("\n[Environment Files]")
    root = Path(__file__).parent.parent
    
    files_to_check = {
        'requirements.txt': 'Production dependencies',
        'requirements-dev.txt': 'Development dependencies',
        '.gitignore': 'Git ignore rules',
        '.env.example': 'Environment example',
        '00_admin/WORKSPACE_RULES.md': 'Workspace rules',
    }
    
    all_ok = True
    for file, description in files_to_check.items():
        file_path = root / file
        if file_path.exists():
            print(f"  ✓ {file:<30} - {description}")
        else:
            print(f"  ✗ {file:<30} - {description} (MISSING)")
            all_ok = False
    
    return all_ok


def main():
    """Run smoke test"""
    print_header("Smoke Test - DB_LIBRARY_EDIT Python Environment")
    
    # Check Python version
    print("\n[Python Info]")
    py_ok = check_python_version()
    
    # Check imports
    print("\n[Package Imports]")
    required_ok, optional_ok = check_imports()
    
    # Check environment files
    print("\n[Environment Setup]")
    env_ok = check_environment_files()
    
    # Summary
    print_header("Test Summary")
    
    status_list = [
        ("Python Version", py_ok),
        ("Required Packages", required_ok),
        ("Environment Files", env_ok),
    ]
    
    print()
    for name, status in status_list:
        symbol = "✓ PASS" if status else "✗ FAIL"
        color = "\033[92m" if status else "\033[91m"  # Green or Red
        reset = "\033[0m"
        print(f"  {color}{symbol}{reset} - {name}")
    
    # Overall result
    overall = py_ok and required_ok and env_ok
    result_symbol = "\033[92m✓ PASS\033[0m" if overall else "\033[91m✗ FAIL\033[0m"
    print(f"\n{'='*50}")
    print(f"  Overall Result: {result_symbol}")
    print(f"{'='*50}\n")
    
    return 0 if overall else 1


if __name__ == '__main__':
    sys.exit(main())
