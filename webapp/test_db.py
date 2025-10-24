from app import app
from db import get_db

try:
    db = get_db()
    print("✓ Conexão com MySQL OK!")
    db.close()
except Exception as e:
    print(f"✗ Erro na conexão: {e}")
