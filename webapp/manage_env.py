# webapp/manage_env.py
import os
import subprocess
import shutil
from pathlib import Path
import time
import signal
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ENVS_DIR = Path("/vagrant/environments")
ENVS_DIR.mkdir(exist_ok=True)

# Detectar se está usando cgroups v2
CGROUP_V2 = Path("/sys/fs/cgroup/cgroup.controllers").exists()
CGROUP_BASE = Path("/sys/fs/cgroup")

# Configurações fixas da VM
VM_TOTAL_MEM = 4096  # MB
VM_TOTAL_CPU = 2     # cores

def run_cmd(cmd, cwd=None, shell=False, check=False):
    """Executa comando com tratamento ULTRA-ROBUSTO de encoding."""
    try:
        if isinstance(cmd, list):
            proc = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE, text=False, check=check)
        else:
            proc = subprocess.run(cmd, cwd=cwd, shell=shell, stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE, text=False, check=check)
        
        try:
            stdout_text = proc.stdout.decode('utf-8', errors='replace')
        except UnicodeDecodeError:
            stdout_text = proc.stdout.decode('latin-1', errors='replace')
            
        try:
            stderr_text = proc.stderr.decode('utf-8', errors='replace')
        except UnicodeDecodeError:
            stderr_text = proc.stderr.decode('latin-1', errors='replace')
        
        return proc.returncode, stdout_text, stderr_text
        
    except subprocess.CalledProcessError as e:
        try:
            stdout_text = e.stdout.decode('utf-8', errors='replace') if e.stdout else ""
            stderr_text = e.stderr.decode('utf-8', errors='replace') if e.stderr else ""
        except UnicodeDecodeError:
            stdout_text = e.stdout.decode('latin-1', errors='replace') if e.stdout else ""
            stderr_text = e.stderr.decode('latin-1', errors='replace') if e.stderr else ""
        return e.returncode, stdout_text, stderr_text
    except Exception as e:
        try:
            safe_error = str(e).encode('utf-8', errors='replace').decode('utf-8')
        except:
            safe_error = "Erro desconhecido"
        return 1, "", safe_error

def read_file_sudo(filepath):
    """Lê arquivo usando sudo."""
    try:
        r, out, err = run_cmd(["sudo", "cat", str(filepath)])
        if r == 0 and out.strip():
            return out.strip()
        return None
    except Exception:
        return None

def write_log(log_file, content):
    """Escreve no log usando sudo."""
    try:
        log_dir = log_file.parent
        run_cmd(["sudo", "mkdir", "-p", str(log_dir)])
        run_cmd(["sudo", "chown", "www-data:www-data", str(log_dir)])
        run_cmd(["sudo", "chmod", "755", str(log_dir)])
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        run_cmd(["sudo", "cp", tmp_path, str(log_file)])
        run_cmd(["sudo", "chown", "www-data:www-data", str(log_file)])
        run_cmd(["sudo", "chmod", "644", str(log_file)])
        os.unlink(tmp_path)
        return True
    except Exception as e:
        print(f"Erro ao escrever log: {e}")
        return False

def get_current_usage():
    """Calcula CPU e memória já alocados em ambientes existentes."""
    total_cpu = 0
    total_mem = 0
    for env_dir in ENVS_DIR.iterdir():
        if env_dir.is_dir():
            db_path = env_dir / "env.pid"
            if db_path.exists():
                cpu_file = env_dir / "cpu_alloc.txt"
                mem_file = env_dir / "mem_alloc.txt"
                try:
                    if cpu_file.exists():
                        total_cpu += float(read_file_sudo(cpu_file) or 0)
                    if mem_file.exists():
                        total_mem += int(read_file_sudo(mem_file) or 0)
                except:
                    continue
    return total_cpu, total_mem

def create_env(name, cpu_percent=100, mem=1024, io=10):
    """Cria um ambiente isolado com limite de CPU em porcentagem e memória da VM."""
    VM_TOTAL_CPU = 2      # Total de CPUs da VM
    VM_TOTAL_MEM = 4096   # Memória total da VM em MB

    env_path = ENVS_DIR / name
    log_file = env_path / "logs" / f"{name}.log"
    workdir = env_path / "workspace"
    cgroup_name = f"cloudenv_{name}"

    # ✅ VALIDAÇÃO: Verificar memória
    if mem > VM_TOTAL_MEM:
        return 1, "", f"Erro: Memória solicitada ({mem} MB) excede limite da VM ({VM_TOTAL_MEM} MB)", ""

    # ✅ VALIDAÇÃO: Verificar CPU
    max_cpu_percent = VM_TOTAL_CPU * 100  # 200% (2 cores = 200%)
    if cpu_percent > max_cpu_percent:
        return 1, "", f"Erro: CPU solicitada ({cpu_percent}%) excede limite da VM ({max_cpu_percent}%)", ""

    # Criar estrutura de diretórios
    for subdir in ['', 'logs', 'workspace']:
        dir_path = env_path / subdir if subdir else env_path
        if not dir_path.exists():
            run_cmd(["sudo", "mkdir", "-p", str(dir_path)])
            run_cmd(["sudo", "chown", "www-data:www-data", str(dir_path)])
            run_cmd(["sudo", "chmod", "755", str(dir_path)])

    pid_file = env_path / "env.pid"

    write_log(log_file, f"=== Criando ambiente {name} ===\n")
    write_log(log_file, f"CPU: {cpu_percent}% | Memoria: {mem} MB | I/O: {io} MB/s\n")

    # ✅ CORRIGIDO: Configurar cgroups v2 com cálculo correto
    if CGROUP_V2:
        cgroup_path = CGROUP_BASE / cgroup_name
        try:
            run_cmd(["sudo", "mkdir", "-p", str(cgroup_path)])

            # ✅ CPU - CÁLCULO CORRETO
            # cpu.max formato: "MAX PERIOD" em microsegundos
            # Período padrão: 100000 (100ms)
            # Para X% de CPU: quota = (X * 100000) / 100
            # Exemplo: 50% de 1 core = 50000 microsegundos de 100000
            # Exemplo: 150% (1.5 cores) = 150000 microsegundos de 100000
            
            period = 100000  # 100ms em microsegundos
            quota = int((cpu_percent * period) / 100)  # ✅ FÓRMULA CORRETA
            
            write_log(log_file, f"Configurando CPU: {cpu_percent}% = {quota} de {period} microsegundos\n")
            run_cmd(["sudo", "bash", "-c", f"echo '{quota} {period}' > {cgroup_path}/cpu.max 2>/dev/null || true"])

            # ✅ Memória - já estava correto
            if mem > 0:
                mem_bytes = mem * 1024 * 1024
                write_log(log_file, f"Configurando Memória: {mem} MB = {mem_bytes} bytes\n")
                run_cmd(["sudo", "bash", "-c", f"echo {mem_bytes} > {cgroup_path}/memory.max 2>/dev/null || true"])
                # Também configurar memory.high (soft limit)
                mem_high = int(mem_bytes * 0.9)  # 90% do limite como soft limit
                run_cmd(["sudo", "bash", "-c", f"echo {mem_high} > {cgroup_path}/memory.high 2>/dev/null || true"])

            # I/O
            if io > 0:
                io_bps = io * 1024 * 1024
                write_log(log_file, f"Configurando I/O: {io} MB/s = {io_bps} bytes/s\n")
                run_cmd(["sudo", "bash", "-c", f"echo '8:0 rbps={io_bps} wbps={io_bps}' > {cgroup_path}/io.max 2>/dev/null || true"])

            write_log(log_file, "✓ Cgroups v2 configurados com limites corretos\n")
        except Exception as e:
            write_log(log_file, f"⚠ Erro ao configurar cgroups: {e}\n")

    # Criar script init.sh
    init_script = env_path / "init.sh"
    init_content = f"""#!/bin/bash
echo "=== INICIANDO NAMESPACE ISOLADO ===" >> {log_file}
echo "PID no namespace: $$" >> {log_file}
mount -t proc proc /proc
echo "PROC montado dentro do namespace" >> {log_file}
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME=/root
hostname env-{name}
echo "Hostname: $(hostname)" >> {log_file}
echo "=== PROCESSOS NO NAMESPACE (DEVE SER POUCOS) ===" >> {log_file}
ps aux >> {log_file}
echo "=== FILESYSTEMS MONTADOS ===" >> {log_file}
mount | grep -E "(proc|sys)" >> {log_file}
echo "Namespace PID isolado configurado!" >> {log_file}
exec tail -f /dev/null
"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as tmp:
        tmp.write(init_content)
        tmp_path = tmp.name

    run_cmd(["sudo", "cp", tmp_path, str(init_script)])
    run_cmd(["sudo", "chmod", "755", str(init_script)])
    run_cmd(["sudo", "chown", "www-data:www-data", str(init_script)])
    os.unlink(tmp_path)

    # Iniciar processo isolado
    try:
        write_log(log_file, "Iniciando processo com PID namespace isolado...\n")

        if CGROUP_V2:
            cmd = [
                "sudo", "unshare",
                "--fork", "--pid", "--mount-proc", "--uts", "--ipc", "--net",
                "bash", "-c", f"cd {workdir} && exec {init_script}"
            ]
        else:
            cmd = [
                "sudo", "cgexec",
                "-g", f"cpu:{cgroup_name}",
                "-g", f"memory:{cgroup_name}",
                "unshare", "--fork", "--pid", "--mount-proc", "--uts", "--ipc", "--net",
                "bash", "-c", f"cd {workdir} && exec {init_script}"
            ]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        host_pid = proc.pid
        run_cmd(["sudo", "bash", "-c", f"echo {host_pid} > {pid_file}"])
        run_cmd(["sudo", "chown", "www-data:www-data", str(pid_file)])
        write_log(log_file, f"PID do host: {host_pid}\n")
        time.sleep(3)

        # Verificar se processo está vivo
        r, _, _ = run_cmd(["sudo", "kill", "-0", str(host_pid)])
        if r == 0:
            if CGROUP_V2:
                # ✅ Adicionar processo ao cgroup
                write_log(log_file, f"Adicionando PID {host_pid} ao cgroup {cgroup_name}...\n")
                run_cmd(["sudo", "bash", "-c", f"echo {host_pid} > /sys/fs/cgroup/{cgroup_name}/cgroup.procs 2>/dev/null || true"])
                
                # Verificar se foi adicionado
                r_check, procs_out, _ = run_cmd(["sudo", "cat", f"/sys/fs/cgroup/{cgroup_name}/cgroup.procs"])
                if str(host_pid) in procs_out:
                    write_log(log_file, f"✓ PID {host_pid} adicionado ao cgroup com sucesso\n")
                else:
                    write_log(log_file, f"⚠ PID pode não estar no cgroup\n")

            # Verificar isolamento
            try:
                test_cmd = [
                    "sudo", "nsenter", "-t", str(host_pid), "-m", "-u", "-i", "-n", "-p", "ps", "aux"
                ]
                r2, out, err = run_cmd(test_cmd)
                line_count = len([line for line in out.split('\n') if line.strip() and not line.startswith('USER')])

                write_log(log_file, f"✓ Ambiente criado com {line_count} processos visíveis no namespace\n")
                write_log(log_file, f"✓ Status: running\n\n")
                return 0, "Ambiente criado com sucesso", "", str(env_path)

            except Exception as e:
                write_log(log_file, f"⚠ Ambiente criado (verificação falhou): {str(e)}\n")
                return 0, "Ambiente criado", "", str(env_path)
        else:
            write_log(log_file, f"✗ Processo morreu\n")
            return 1, "", "Processo não sobreviveu", ""

    except Exception as e:
        write_log(log_file, f"✗ Erro: {str(e)}\n")
        import traceback
        write_log(log_file, f"{traceback.format_exc()}\n")
        return 1, "", str(e), ""


def status_env(name):
    """Verifica status do ambiente - VERSÃO CORRIGIDA."""
    env_path = ENVS_DIR / name
    if not env_path.exists():
        return "not_found"
    
    pid_file = env_path / "env.pid"
    pid_content = read_file_sudo(pid_file)
    
    if pid_content:
        try:
            # Este é o PID do HOST
            host_pid = int(pid_content)
            
            # Verificar se o processo HOST ainda está vivo (MÉTODO SIMPLES)
            r, _, _ = run_cmd(["sudo", "kill", "-0", str(host_pid)])
            
            if r == 0:
                # Processo host está vivo - considerar como RUNNING
                return "running"
            else:
                return "stopped"
                
        except (ValueError, ProcessLookupError):
            return "stopped"
    
    return "stopped"

def halt_env(name):
    """Para o ambiente."""
    env_path = ENVS_DIR / name
    pid_file = env_path / "env.pid"
    log_file = env_path / "logs" / f"{name}.log"
    
    pid_content = read_file_sudo(pid_file)
    
    if pid_content:
        try:
            # Este é o PID do HOST
            host_pid = int(pid_content)
            
            write_log(log_file, f"\n=== Parando ambiente (PID host: {host_pid}) ===\n")
            
            # Parar processo host (isso para todo o namespace)
            run_cmd(["sudo", "kill", "-15", str(host_pid)])
            time.sleep(2)
            
            # Verificar se ainda está vivo
            r, _, _ = run_cmd(["sudo", "kill", "-0", str(host_pid)])
            if r == 0:
                write_log(log_file, "Forcando parada com SIGKILL...\n")
                run_cmd(["sudo", "kill", "-9", str(host_pid)])
                time.sleep(1)
            
            # Remover PID file
            run_cmd(["sudo", "rm", "-f", str(pid_file)])
            write_log(log_file, f"=== Ambiente parado ===\n{time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
        except Exception as e:
            write_log(log_file, f"Erro ao parar ambiente: {e}\n")
    
    return 0, "", ""

def resume_env(name):
    """Retoma ambiente parado."""
    # Chama create_env mas retorna apenas 3 valores para compatibilidade
    try:
        r, out, err, path = create_env(name)
        return r, out, err  # Retorna apenas 3 valores
    except Exception as e:
        return 1, "", f"Erro ao retomar ambiente: {str(e)}"

def destroy_env(name):
    """Remove o ambiente completamente."""
    # Parar o ambiente primeiro
    halt_env(name)
    
    env_path = ENVS_DIR / name
    cgroup_name = f"cloudenv_{name}"
    
    # Remover cgroup
    if CGROUP_V2:
        cgroup_path = CGROUP_BASE / cgroup_name
        if cgroup_path.exists():
            try:
                procs_file = cgroup_path / "cgroup.procs"
                procs_content = read_file_sudo(procs_file)
                if procs_content:
                    for pid_line in procs_content.split('\n'):
                        pid = pid_line.strip()
                        if pid and pid.isdigit():
                            run_cmd(["sudo", "kill", "-9", pid])
                time.sleep(1)
                run_cmd(["sudo", "rmdir", str(cgroup_path)])
            except Exception as e:
                print(f"Aviso ao remover cgroup: {e}")
    
    # Remover diretório
    if env_path.exists():
        run_cmd(["sudo", "rm", "-rf", str(env_path)])
    
    return 0, "", ""

def exec_in_env(name, command, background=False):
    """Executa comando no ambiente - VERSÃO CORRIGIDA."""
    env_path = ENVS_DIR / name
    if not env_path.exists():
        return 1, "", "Ambiente não encontrado"
    
    if status_env(name) != "running":
        return 1, "", "Ambiente não está rodando"
    
    log_file = env_path / "logs" / f"{name}.log"
    workdir = env_path / "workspace"
    pid_file = env_path / "env.pid"
    
    # Ler PID do ambiente (PID do HOST)
    pid_content = read_file_sudo(pid_file)
    if not pid_content:
        return 1, "", "PID do ambiente não encontrado"
    
    try:
        host_pid = int(pid_content)
    except ValueError:
        return 1, "", "PID inválido"
    
    # Escrever log de início
    safe_log_content = f"\n=== Executando: {command} ===\n{time.strftime('%Y-%m-%d %H:%M:%S')}\nBackground: {background}\n\n"
    write_log(log_file, safe_log_content)
    
    try:
        if background:
            # CORREÇÃO: Comando background - garantir que escreve no log
            background_script = env_path / f"bg_{int(time.time())}.sh"
            
            # Script que redireciona TODO output para o log do ambiente
            script_content = f"""#!/bin/bash
cd {workdir}
echo "INICIANDO BACKGROUND: {command}" >> {log_file}

# Executar o comando e redirecionar TODO output para o log
{command} >> {log_file} 2>&1

# Quando terminar, avisar
echo "BACKGROUND FINALIZADO: Exit code: $?" >> {log_file}
"""
            
            # Criar script
            with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as tmp:
                tmp.write(script_content)
                tmp_path = tmp.name
            
            run_cmd(["sudo", "cp", tmp_path, str(background_script)])
            run_cmd(["sudo", "chmod", "755", str(background_script)])
            run_cmd(["sudo", "chown", "www-data:www-data", str(background_script)])
            os.unlink(tmp_path)
            
            # CORREÇÃO: Executar o script em background DENTRO do namespace
            cmd = f"sudo nsenter -t {host_pid} -m -u -i -n -p bash -c 'nohup {background_script} > /dev/null 2>&1 &'"
            
            # Executar rapidamente
            proc = subprocess.run(
                cmd, 
                shell=True,
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                timeout=5
            )
            
            # Limpar script (ele já foi copiado)
            run_cmd(["sudo", "rm", "-f", str(background_script)])
            
            return 0, "Comando background iniciado - verifique os logs para ver o output", ""
                
        else:
            # Comando foreground (normal)
            cmd = f"sudo nsenter -t {host_pid} -m -u -i -n -p bash -c 'cd {workdir} && {command}'"
            
            proc = subprocess.run(
                cmd, 
                shell=True,
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
            )
            
            # Decodificação segura
            try:
                stdout_text = proc.stdout.decode('utf-8', errors='replace')
            except UnicodeDecodeError:
                stdout_text = proc.stdout.decode('latin-1', errors='replace')
                
            try:
                stderr_text = proc.stderr.decode('utf-8', errors='replace')
            except UnicodeDecodeError:
                stderr_text = proc.stderr.decode('latin-1', errors='replace')
            
            # Preparar output
            output_lines = []
            if stdout_text:
                output_lines.append("STDOUT:")
                output_lines.append(stdout_text)
            if stderr_text:
                output_lines.append("STDERR:")
                output_lines.append(stderr_text)
            
            safe_output = "\n".join(output_lines)
            
            # Escrever no log
            log_output = f"--- Saída ---\n{safe_output}\n--- Código de saída: {proc.returncode} ---\n"
            write_log(log_file, log_output)
            
            return proc.returncode, safe_output, stderr_text
            
    except subprocess.TimeoutExpired:
        safe_error = "Timeout: comando excedeu o tempo limite"
        write_log(log_file, f"✗ {safe_error}\n")
        return 1, "", safe_error
    except Exception as e:
        try:
            error_str = str(e)
            safe_error = error_str.encode('utf-8', errors='replace').decode('utf-8')
        except:
            safe_error = "Erro desconhecido"
        
        write_log(log_file, f"✗ Erro na execução: {safe_error}\n")
        return 1, "", safe_error