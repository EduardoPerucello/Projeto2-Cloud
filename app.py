from flask import Flask, render_template, request, redirect, url_for
import os, mysql.connector, psutil
from run_env import create_environment, terminate_environment

app = Flask(__name__)
BASE_DIR = "/home/vagrant/environments"

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="exec_env"
)
cursor = db.cursor(dictionary=True)

def check_error(output_path):
    """Verifica se o output contém erro"""
    if os.path.exists(output_path):
        with open(output_path) as f:
            content = f.read()
            if "Traceback" in content or "Error" in content:
                return True
    return False

def update_environment_status():
    """Atualiza status de ambientes automaticamente"""
    cursor.execute("SELECT * FROM environments WHERE status='em execução';")
    envs = cursor.fetchall()
    for env in envs:
        output_path = env['output_path']
        env_dir = os.path.dirname(output_path)
        pid_file = os.path.join(env_dir, "pid.txt")
        if os.path.exists(pid_file):
            with open(pid_file) as f:
                pid = int(f.read().strip())
            if psutil.pid_exists(pid):
                continue  # ainda rodando
        # Processo terminou
        error_flag = check_error(output_path)
        cursor.execute(
            "UPDATE environments SET status='terminado', error=%s WHERE id=%s",
            (error_flag, env['id'])
        )
        db.commit()

@app.route("/")
def index():
    update_environment_status()
    cursor.execute("SELECT * FROM environments;")
    envs = cursor.fetchall()
    return render_template("index.html", environments=envs)

@app.route("/run", methods=["POST"])
def run():
    code = request.form['code']
    memory = int(request.form.get('memory', 512))
    cpu = int(request.form.get('cpu', 512))
    io = request.form.get('io', None)

    env_id = create_environment(code, memory_mb=memory, cpu_shares=cpu, io_limit_kbps=io)

    cursor.execute(
        "INSERT INTO environments (id, status, output_path, error) VALUES (%s,%s,%s,%s)",
        (env_id, "em execução", os.path.join(BASE_DIR, env_id, "output.log"), False)
    )
    db.commit()
    return redirect(url_for('index'))

@app.route("/output/<env_id>")
def output(env_id):
    path = os.path.join(BASE_DIR, env_id, "output.log")
    if os.path.exists(path):
        with open(path) as f:
            return "<pre>" + f.read() + "</pre>"
    return "Output não encontrado"

@app.route("/terminate/<env_id>")
def terminate(env_id):
    terminate_environment(env_id)
    path = os.path.join(BASE_DIR, env_id, "output.log")
    error_flag = check_error(path)

    cursor.execute(
        "UPDATE environments SET status='terminado', error=%s WHERE id=%s",
        (error_flag, env_id)
    )
    db.commit()
    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
