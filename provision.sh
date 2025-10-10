#!/bin/bash
set -e

# Força DNS rápido
echo "nameserver 1.1.1.1" | sudo tee /etc/resolv.conf
echo "nameserver 8.8.8.8" | sudo tee -a /etc/resolv.conf

# Atualiza pacotes e instala dependências
apt-get update -y
apt-get install -y apache2 mysql-server git python3 python3-pip cgroup-tools unzip libapache2-mod-wsgi-py3

# Habilita mod_wsgi
a2enmod wsgi
systemctl enable apache2
systemctl start apache2

# Instala pacotes Python
pip3 install flask mysql-connector-python psutil

# Cria diretório base para ambientes
mkdir -p /home/vagrant/environments
chown -R vagrant:vagrant /home/vagrant/environments

# Clona repositório com retry (para não travar)
su - vagrant -c "until git clone https://github.com/EduardoPerucello/Projeto2-Cloud.git /home/vagrant/project; do echo 'Clone falhou, tentando novamente em 5s...'; sleep 5; done"

# Cria banco de dados MySQL e tabela
mysql -e "CREATE DATABASE IF NOT EXISTS exec_env;"
mysql -e "USE exec_env; CREATE TABLE IF NOT EXISTS environments (id VARCHAR(36) PRIMARY KEY, status VARCHAR(20), output_path VARCHAR(255), error BOOLEAN DEFAULT FALSE);"

# Cria run_env.py
cat << 'EOF' > /home/vagrant/project/run_env.py
#!/usr/bin/env python3
import os, uuid, subprocess

BASE_DIR = "/home/vagrant/environments"

def create_environment(script_code, memory_mb=512, cpu_shares=512, io_limit_kbps=None):
    env_id = str(uuid.uuid4())
    env_dir = os.path.join(BASE_DIR, env_id)
    os.makedirs(env_dir, exist_ok=True)

    script_path = os.path.join(env_dir, "script.sh")
    with open(script_path, "w") as f:
        f.write(script_code)

    subprocess.run(f"sudo cgcreate -g memory,cpu,blkio:/{env_id}", shell=True)
    subprocess.run(f"sudo cgset -r memory.limit_in_bytes={memory_mb*1024*1024} {env_id}", shell=True)
    subprocess.run(f"sudo cgset -r cpu.shares={cpu_shares} {env_id}", shell=True)

    if io_limit_kbps:
        kbps = int(io_limit_kbps)
        bps = kbps * 1024
        subprocess.run(f"sudo cgset -r blkio.throttle.write_bps_device='8:0 {bps}' {env_id}", shell=True)

    subprocess.Popen(
        f"sudo unshare -p -m --fork --mount-proc cgexec -g memory,cpu,blkio:/{env_id} bash {script_path} > {env_dir}/output.log 2>&1 & echo $! > {env_dir}/pid.txt",
        shell=True
    )
    return env_id

def terminate_environment(env_id):
    subprocess.run(f"sudo cgdelete -g memory,cpu,blkio:/{env_id}", shell=True)
    env_dir = os.path.join(BASE_DIR, env_id)
    if os.path.exists(env_dir):
        subprocess.run(f"rm -rf {env_dir}", shell=True)
EOF

chmod +x /home/vagrant/project/run_env.py
chown -R vagrant:vagrant /home/vagrant/project

# Configura Apache para servir Flask via WSGI
cat << 'EOF' > /etc/apache2/sites-available/000-default.conf
<VirtualHost *:80>
    ServerAdmin webmaster@localhost
    DocumentRoot /home/vagrant/project

    WSGIDaemonProcess flask_env python-path=/home/vagrant/project
    WSGIScriptAlias / /home/vagrant/project/app.wsgi

    <Directory /home/vagrant/project>
        Require all granted
    </Directory>

    ErrorLog ${APACHE_LOG_DIR}/error.log
    CustomLog ${APACHE_LOG_DIR}/access.log combined
</VirtualHost>
EOF

systemctl restart apache2
