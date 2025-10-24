#!/usr/bin/python3
import sys
import os
import logging

# Configurar logging
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

# Adicionar o diretório webapp ao path
sys.path.insert(0, '/vagrant/webapp')

# Configurar variáveis de ambiente se necessário
os.environ['FLASK_ENV'] = 'production'

try:
    from app import app as application
    logging.info("✓ Flask app carregado com sucesso!")
except Exception as e:
    logging.error(f"✗ Erro ao importar app: {e}")
    import traceback
    logging.error(traceback.format_exc())
    raise

# Para debug
logging.info(f"Python path: {sys.path}")
logging.info(f"Working directory: {os.getcwd()}")