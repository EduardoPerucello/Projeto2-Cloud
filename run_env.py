#!/usr/bin/env python3
import os
import uuid
import subprocess

BASE_DIR = "/home/vagrant/environments"

def create_environment(script_code, memory_mb=512, cpu_shares=512, io_limit_kbps=None):
    """
    Cria um ambiente isolado com namespace + cgroup e executa o script do usuário.
    """
    # Gera um ID único para o ambiente
    env_id = str(uuid.uuid4())
    env_dir = os.path.join(BASE_DIR, env_id)
    
    # Cria diretório do ambiente
    os.makedirs(env_dir, exist_ok=True)

    # Cria script do usuário
    script_path = os.path.join(env_dir, "script.sh")
    with open(script_path, "w") as f:
        f.write(script_code)

    # Cria cgroups para isolar CPU, memória e IO
    subprocess.run(f"sudo cgcreate -g memory,cpu,blkio:/{env_id}", shell=True)
    subprocess.run(f"sudo cgset -r memory.limit_in_bytes={memory_mb*1024*1024} {env_id}", shell=True)
    subprocess.run(f"sudo cgset -r cpu.shares={cpu_shares} {env_id}", shell=True)

    if io_limit_kbps:
        kbps = int(io_limit_kbps)
        bps = kbps * 1024
        subprocess.run(f"sudo cgset -r blkio.throttle.write_bps_device='8:0 {bps}' {env_id}", shell=True)

    # Executa script dentro do namespace e cgroup, salva PID e output
    subprocess.Popen(
        f"sudo unshare -p -m --fork --mount-proc cgexec -g memory,cpu,blkio:/{env_id} "
        f"bash {script_path} > {env_dir}/output.log 2>&1 & echo $! > {env_dir}/pid.txt",
        shell=True
    )

    return env_id


def terminate_environment(env_id):
    """
    Remove cgroup e pasta do ambiente
    """
    subprocess.run(f"sudo cgdelete -g memory,cpu,blkio:/{env_id}", shell=True)
    env_dir = os.path.join(BASE_DIR, env_id)
    if os.path.exists(env_dir):
        subprocess.run(f"rm -rf {env_dir}", shell=True)
