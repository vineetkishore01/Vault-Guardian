#!/usr/bin/env python
"""Reset Vault Guardian data for testing - makes project virgin again."""
import os
import shutil
from pathlib import Path

def reset_data():
    """Delete all data files to start fresh."""
    project_root = Path(__file__).parent
    
    # Directories to clean
    dirs_to_clean = [
        project_root / "data",
        project_root / "logs",
        project_root / "reports",
    ]
    
    # Files to delete
    files_to_delete = [
        project_root / ".pytest_cache",
    ]
    
    print("🧹 Resetting Vault Guardian data...")
    
    # Clean directories
    for dir_path in dirs_to_clean:
        if dir_path.exists():
            print(f"  Deleting: {dir_path}")
            shutil.rmtree(dir_path)
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"  Recreated: {dir_path}")
        else:
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"  Created: {dir_path}")
    
    # Delete files
    for file_path in files_to_delete:
        if file_path.exists():
            print(f"  Deleting: {file_path}")
            if file_path.is_dir():
                shutil.rmtree(file_path)
            else:
                file_path.unlink()
    
    print("✅ Reset complete! Project is now virgin.")
    print("📝 Next steps:")
    print("   1. Run: python -m src.main")
    print("   2. Test your bot")
    print("   3. Run this script again to reset: python reset_data.py")

if __name__ == "__main__":
    confirm = input("⚠️  This will delete ALL data. Continue? (yes/no): ")
    if confirm.lower() == "yes":
        reset_data()
    else:
        print("❌ Reset cancelled.")
