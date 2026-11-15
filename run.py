"""入口脚本：不装包、不设 PYTHONPATH，从任意目录都能跑。

仓库内用法与 ``python -m ceds`` 等价：

    python run.py run --customers customers.csv --out out/

装成技能后从别的项目调用（Windows）：

    python -X utf8 "C:\\Users\\<你>\\.dsh\\skills\\customer-email-deep-search\\run.py" run --customers customers.csv --out out/
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from ceds.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
