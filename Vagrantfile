Vagrant.configure("2") do |config|
  config.vm.box = "bento/ubuntu-22.04"
  config.vm.network "private_network", ip: "192.168.56.10"
  config.vm.hostname = "exec-env"
  
  config.vm.provider "vmware_desktop" do |vmw|
    vmw.gui = true
    vmw.cpus = 2
    vmw.memory = 4096
    vmw.vmx["displayName"] = "Cloud Exec Environment"
  end
  
  config.vm.synced_folder ".", "/vagrant"
  
  config.vm.provision "shell", inline: <<-SHELL
    set -e
    
    echo "====================================="
    echo "Iniciando configuração do ambiente..."
    echo "====================================="
    
    # Atualizar pacotes
    apt-get update
    
    # Instalar dependências principais
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
      python3 python3-pip \
      mysql-server \
      apache2 libapache2-mod-wsgi-py3 \
      cgroup-tools \
      stress \
      htop \
      net-tools
    
    echo "✓ Pacotes instalados"
    
    # Instalar dependências Python
    pip3 install flask mysql-connector-python
    
    echo "✓ Dependências Python instaladas"
    
    # Configurar MySQL para aceitar conexões remotas
    sed -i "s/^bind-address.*/bind-address = 0.0.0.0/" /etc/mysql/mysql.conf.d/mysqld.cnf
    systemctl restart mysql
    
    echo "✓ MySQL configurado"
    
    # Criar base de dados e tabelas
    mysql -u root <<EOF
CREATE DATABASE IF NOT EXISTS cloud_project;
CREATE USER IF NOT EXISTS 'cloud_user'@'%' IDENTIFIED BY 'cloud_pass';
GRANT ALL PRIVILEGES ON cloud_project.* TO 'cloud_user'@'%';
FLUSH PRIVILEGES;

USE cloud_project;

CREATE TABLE IF NOT EXISTS environments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL UNIQUE,
  cpu INT NOT NULL,
  mem INT NOT NULL,
  io INT DEFAULT 10,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  status VARCHAR(30) DEFAULT 'creating',
  container_path VARCHAR(255),
  last_command TEXT,
  log_path VARCHAR(255),
  INDEX idx_name (name),
  INDEX idx_status (status)
);
EOF
    
    echo "✓ Banco de dados criado"
    
    # Criar diretórios necessários
    mkdir -p /vagrant/environments
    mkdir -p /vagrant/webapp/templates
    chmod 755 /vagrant/environments
    
    echo "✓ Diretórios criados"
    
    # Verificar cgroups v1 (usado pelo código)
    echo "Verificando cgroups..."
    if [ -d "/sys/fs/cgroup/cpu" ]; then
      echo "✓ Cgroups v1 disponíveis"
    else
      echo "⚠ Cgroups v1 não encontrados - podem ser necessários ajustes"
    fi
    
    # Configurar Apache
    rm -f /etc/apache2/sites-enabled/000-default.conf
    
    cat <<'APACHECONF' >/etc/apache2/sites-available/flaskapp.conf
<VirtualHost *:80>
  ServerAdmin webmaster@localhost
  DocumentRoot /vagrant/webapp
  
  WSGIDaemonProcess flaskapp python-path=/vagrant/webapp user=www-data group=www-data processes=2 threads=5
  WSGIProcessGroup flaskapp
  WSGIScriptAlias / /vagrant/webapp/flaskapp.wsgi
  
  <Directory /vagrant/webapp>
    Require all granted
    Options -Indexes
  </Directory>
  
  ErrorLog ${APACHE_LOG_DIR}/flaskapp_error.log
  CustomLog ${APACHE_LOG_DIR}/flaskapp_access.log combined
  LogLevel warn
</VirtualHost>
APACHECONF
    
    a2ensite flaskapp.conf
    
    echo "✓ Apache configurado"
    
    # Dar permissões para www-data executar comandos com sudo
    echo "www-data ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/apache-isolation
    chmod 0440 /etc/sudoers.d/apache-isolation
    
    echo "✓ Sudoers configurado"
    
    # Garantir permissões corretas
    chown -R www-data:www-data /vagrant/environments 2>/dev/null || true
    
    # Reiniciar Apache
    systemctl restart apache2
    
    echo ""
    echo "======================================"
    echo "✓ Setup completo!"
    echo "======================================"
    echo "Acesse: http://192.168.56.10"
    echo "MySQL: cloud_user@192.168.56.10"
    echo "======================================"
    echo ""
    echo "Comandos úteis:"
    echo "  vagrant ssh          - Conectar na VM"
    echo "  vagrant reload       - Recarregar VM"
    echo "  vagrant halt         - Desligar VM"
    echo "  vagrant destroy      - Destruir VM"
    echo ""
    echo "Logs do Apache:"
    echo "  sudo tail -f /var/log/apache2/flaskapp_error.log"
    echo "======================================"
  SHELL
end