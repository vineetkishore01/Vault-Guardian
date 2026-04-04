#!/usr/bin/env python
"""Manual backup for Vault Guardian data."""
import os
import shutil
from pathlib import Path
from datetime import datetime

def backup_data():
    """Create a manual backup of all data."""
    project_root = Path(__file__).parent
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = project_root / "backups" / timestamp
    
    print(f"💾 Creating backup: {backup_dir}")
    
    # Create backup directory
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy data directory
    data_dir = project_root / "data"
    if data_dir.exists():
        shutil.copytree(data_dir, backup_dir / "data")
        print(f"  ✅ Backed up: data/")
    
    # Copy logs directory
    logs_dir = project_root / "logs"
    if logs_dir.exists():
        shutil.copytree(logs_dir, backup_dir / "logs")
        print(f"  ✅ Backed up: logs/")
    
    # Copy reports directory
    reports_dir = project_root / "reports"
    if reports_dir.exists():
        shutil.copytree(reports_dir, backup_dir / "reports")
        print(f"  ✅ Backed up: reports/")
    
    # Copy .env file
    env_file = project_root / ".env"
    if env_file.exists():
        shutil.copy2(env_file, backup_dir / ".env")
        print(f"  ✅ Backed up: .env")
    
    print(f"✅ Backup complete: {backup_dir}")
    print(f"📦 Size: {sum(f.stat().st_size for f in backup_dir.rglob('*') if f.is_file()) / 1024 / 1024:.2f} MB")

if __name__ == "__main__":
    backup_data()
