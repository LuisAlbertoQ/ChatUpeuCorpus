"""Configuración de pytest para los tests del backend.

Añade /app (directorio montado del backend) al sys.path para que
`import rag_pipeline`, `import config` y `import logger` resuelvan
igual que en la aplicación FastAPI.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
