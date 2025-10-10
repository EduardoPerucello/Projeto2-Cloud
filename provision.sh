#!/bin/bash

set -e  # Para o script se qualquer comando falhar

echo "[1/10] ➤ Forçando DNS Google para garantir internet..."
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf

echo "[2/10] ➤ Atualizando pacotes do sistema..."
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -y
sudo apt-get upgrade -y

echo "[3/10] ➤ Instalando dependências base (git, python3, pip)..."
sudo apt-get install -y git python3 python3-pip

echo "[4/10] ➤ Limpando diretório antigo do projeto, se existir..."
sudo rm -rf /home/vagrant/project

echo "[5/10] ➤ Clonando repositório do GitHub com depth=1 para acelerar..."
git clone --depth 1 https://github.com/EduardoPerucello/Projeto2-Cloud.git /home/vagrant/project

echo "[6/10] ➤ Instalando Apache, mod_wsgi e MySQL em modo não interativo..."
export DEBIAN_FRONTEND=noninteractive
sudo apt-get install -y apache2 libapache2-mod-wsgi-py3 mysql-server

echo "[7/10] ➤ Instalando dependências Python do projeto..."
cd /home/vagrant/project
pip3 install -r requirements.txt || echo "[INFO] Nenhum requirements.txt encontrado, seguindo."

echo "[8/10] ➤ Configurando Apache para servir Flask via WSGI..."
sudo tee /etc/apache2/sites-available/flaskapp.conf > /dev/null << EOF
<VirtualHost *:80>
    ServerName flaskapp.local
    WSGIDaemonProcess flaskapp threads=5 python-path=/home/vagrant/project
    WSGIScriptAlias / /home/vagrant/project/app.wsgi

    <Directory /home/vagrant/project>
        Require all granted
    </Directory>

    Alias /static /home/vagrant/project/static
    <Directory /home/vagrant/project/static/>
        Require all granted
    </Directory>

    ErrorLog \${APACHE_LOG_DIR}/flaskapp_error.log
    CustomLog \${APACHE_LOG_DIR}/flaskapp_access.log combined
</VirtualHost>
EOF

echo "[9/10] ➤ Ativando site Flask no Apache..."
sudo a2dissite 000-default.conf || true
sudo a2ensite flaskapp.conf
sudo systemctl restart apache2

echo "[10/10] ✅ AMBIENTE CONFIGURADO COM SUCESSO!"
echo "Acesse via navegador: http://127.0.0.1:8080 ou http://flaskapp.local (se mapeado no hosts)"
