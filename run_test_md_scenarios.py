#!/usr/bin/env python3
"""
Root-level wrapper runner for test.md scenarios.
Tự động chuyển đường dẫn vào ChatbotN8n/javis/server/ và thực thi run_test_md_scenarios.py.
"""
import os
import sys
from pathlib import Path

# Thêm đường dẫn ChatbotN8n/javis/server vào sys.path và chdir
SERVER_DIR = Path(__file__).parent / "ChatbotN8n" / "javis" / "server"
if SERVER_DIR.exists():
    os.chdir(SERVER_DIR)
    sys.path.insert(0, str(SERVER_DIR))
    
    # Import và thực thi main của run_test_md_scenarios
    import asyncio
    from run_test_md_scenarios import main
    asyncio.run(main())
else:
    print(f"❌ Không tìm thấy thư mục server tại {SERVER_DIR}")
    sys.exit(1)
