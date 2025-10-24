from app import app
from flask import render_template

try:
    with app.app_context():
        result = render_template('index.html', envs=[])
        print("✓ Template OK!")
except Exception as e:
    print(f"✗ Erro no template: {e}")
    import traceback
    traceback.print_exc()
