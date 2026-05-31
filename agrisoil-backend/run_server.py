"""
Script para iniciar o backend AgriSoil
"""
import sys
import os

# Adicionar diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importar e iniciar
from app.main import app
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "127.0.0.1")
    print("Iniciando AgriSoil Backend...")
    print(f"URL: http://{host}:{port}")
    print(f"Docs: http://{host}:{port}/docs")
    print()
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )
