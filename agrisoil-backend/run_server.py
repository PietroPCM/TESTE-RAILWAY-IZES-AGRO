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
    port = 8000
    print("🚀 Iniciando AgriSoil Backend...")
    print(f"📍 URL: http://127.0.0.1:{port}")
    print(f"📚 Docs: http://127.0.0.1:{port}/docs")
    print()
    
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info"
    )
