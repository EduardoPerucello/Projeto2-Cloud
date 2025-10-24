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

# --- Ativar virtualenv ---
venv_path = '/vagrant/webapp/venv'
activate_this = os.path.join(venv_path, 'bin', 'activate_this.py')
if os.path.exists(activate_this):
    with open(activate_this) as f:
        exec(f.read(), dict(__file__=activate_this))
    logging.info(f"✓ Virtualenv ativado: {venv_path}")
else:
    logging.warning(f"⚠ Virtualenv não encontrado em {venv_path}, usando Python do sistema")

# --- Importar app ---
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
