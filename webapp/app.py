# webapp/app.py
from flask import Flask, render_template, request, redirect, url_for, send_file
from db import get_db
from manage_env import create_env, status_env, exec_in_env, halt_env, destroy_env, resume_env
import os

app = Flask(__name__)

@app.route('/')
def index():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM environments ORDER BY created_at DESC")
    envs = cur.fetchall()
    
    # Atualizar status real de cada ambiente
    for env in envs:
        real_status = status_env(env['name'])
        if real_status != env['status'] and real_status != 'not_found':
            # Atualizar no banco se o status mudou
            cur2 = db.cursor()
            cur2.execute("UPDATE environments SET status=%s WHERE name=%s", 
                        (real_status, env['name']))
            db.commit()
            cur2.close()
            env['status'] = real_status
    
    cur.close()
    db.close()
    return render_template('index.html', envs=envs)

@app.route('/create', methods=['POST'])
def create():
    name = request.form['name']
    cpu_percent = int(request.form['cpu'])  # ✅ CORRIGIDO: renomeado para cpu_percent
    mem = int(request.form['mem'])
    io = int(request.form.get('io', 10))
    
    # Verificar se já existe
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT name FROM environments WHERE name=%s", (name,))
    if cur.fetchone():
        cur.close()
        db.close()
        return redirect(url_for('index'))
    
    cur.execute(
        "INSERT INTO environments (name, cpu, mem, io, status) VALUES (%s,%s,%s,%s,%s)",
        (name, cpu_percent, mem, io, 'creating')  # ✅ Salva a porcentagem no banco
    )
    db.commit()
    cur.close()
    db.close()
    
    # Criar ambiente - ✅ CORRIGIDO: passa cpu_percent
    try:
        r, out, err, path = create_env(name, cpu_percent=cpu_percent, mem=mem, io=io)
        status = 'running' if r == 0 else 'error'
    except Exception as e:
        print(f"Erro ao criar ambiente: {e}")
        r, out, err, path = 1, "", str(e), None
        status = 'error'
    
    db = get_db()
    cur = db.cursor()
    log_path = os.path.join("/vagrant/environments", name, "logs", f"{name}.log")
    cur.execute(
        "UPDATE environments SET status=%s, container_path=%s, log_path=%s WHERE name=%s",
        (status, path if r == 0 else None, log_path, name)
    )
    db.commit()
    cur.close()
    db.close()
    
    return redirect(url_for('index'))

@app.route('/exec/<name>', methods=['POST'])
def execcmd(name):
    cmd = request.form['command']
    bg = request.form.get('background') == '1'
    
    r, out, err = exec_in_env(name, cmd, background=bg)
    
    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE environments SET last_command=%s WHERE name=%s", (cmd, name))
    db.commit()
    cur.close()
    db.close()
    
    return redirect(url_for('index'))

@app.route('/logs/<name>')
def logs(name):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT log_path FROM environments WHERE name=%s", (name,))
    row = cur.fetchone()
    cur.close()
    db.close()
    
    if not row:
        return "Ambiente não encontrado", 404
    
    lp = row['log_path']
    if not lp or not os.path.exists(lp):
        return "Log não encontrado. O ambiente pode não ter sido criado corretamente.", 404
    
    return send_file(lp, mimetype='text/plain')

@app.route('/stop/<name>', methods=['POST'])
def stop(name):
    halt_env(name)
    
    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE environments SET status=%s WHERE name=%s", ("stopped", name))
    db.commit()
    cur.close()
    db.close()
    
    return redirect(url_for('index'))

@app.route('/resume/<name>', methods=['POST'])
def resume(name):
    r, out, err = resume_env(name)
    
    db = get_db()
    cur = db.cursor()
    status = 'running' if r == 0 else 'error'
    cur.execute("UPDATE environments SET status=%s WHERE name=%s", (status, name))
    db.commit()
    cur.close()
    db.close()
    
    return redirect(url_for('index'))

@app.route('/destroy/<name>', methods=['POST'])
def destroy(name):
    destroy_env(name)
    
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM environments WHERE name=%s", (name,))
    db.commit()
    cur.close()
    db.close()
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)