import argparse
import tempfile
import yaml
import subprocess
import base64
import os


def load_data_from_yaml(yaml_path,computer_override):
    machine_path = os.path.join(yaml_path,"{}.yaml".format(computer_override))
    machine_data = yaml.safe_load(open(machine_path))
    return machine_data


def rand_fname(suffix=""):
    return base64.b16encode(os.urandom(12)).decode("utf-8") + suffix

def make_scp_command_forward(source_file, dest_file, machine_config):
    return f"scp -P {machine_config['port']} -i {machine_config['ssh_key_path']} {source_file} {machine_config['username']}@{machine_config['ip']}:{dest_file}".split(" ")

def make_scp_command_backward(source_file, dest_file, machine_config):
    return f"scp -P {machine_config['port']} -i {machine_config['ssh_key_path']} {machine_config['username']}@{machine_config['ip']}:{dest_file} {source_file}".split(" ")

def make_ssh_command(machine_config, command):
    ssh_command = f"ssh -p {machine_config['port']} -i {machine_config['ssh_key_path']} {machine_config['username']}@{machine_config['ip']}"
    print(f"{ssh_command} '{command}'")
    final_command = ssh_command.split(" ") + [command]
    return final_command


parser = argparse.ArgumentParser(description='Run a simple command')
parser.add_argument('--copy-forward', nargs='*', default=["./"], help='Files and folders to copy when running the command. Defaults to everything in the current working directory')
parser.add_argument('--copy-backwards', nargs='*', default=["./"], help='Files and folders to copy back from the worker running the command. Defaults to everything in the current working directory')
parser.add_argument('--machine', default="local", help='machine id')
parser.add_argument('--job-name', default="__random__", help='job name')
parser.add_argument('command', nargs='*')

args = parser.parse_args()
yaml_path = os.path.expanduser("~/.local/var/")
machine_config = load_data_from_yaml(yaml_path, args.machine)

job_name = rand_fname() if args.job_name == "__random__" else args.job_name
job_result_folder = os.path.expanduser("~/job_results/")+job_name
if os.path.exists(job_result_folder):
    raise RuntimeError(f"results for job '{job_name}' already exist, move or remove files before continuing")

with tempfile.NamedTemporaryFile(suffix=".tar") as tarfile:
    fname = tarfile.name

    print("preparing files for transfer:")
    tararg = f"tar cf {fname} {' '.join(args.copy_forward)}".split(" ")
    print(" ".join(tararg))
    subprocess.run(tararg)

    print("transfering files to remote:")
    remote_tar_fname = "/tmp/"+rand_fname(".tar")
    copy_forward_cmd = make_scp_command_forward(fname, remote_tar_fname, machine_config)
    print(" ".join(copy_forward_cmd))
    subprocess.run(copy_forward_cmd)

if True:
    run_folder = "job_data/"+job_name

    print("unpacking files on remote:")
    unpack_base = f"mkdir -p {run_folder} && cd {run_folder} && tar xf {remote_tar_fname} && rm {remote_tar_fname}"
    unpack_command = make_ssh_command(machine_config, unpack_base)
    subprocess.run(unpack_command)

try:
    print("running command:")
    base_run_command = f"cd {run_folder} && " + " ".join(args.command)
    run_command = make_ssh_command(machine_config, base_run_command)
    subprocess.run(run_command)
except:
    pass

if True:
    print("collecting data on remote:")
    remote_tar_fname_back = "/tmp/"+rand_fname(".tar")
    remote_tararg = f"cd {run_folder} && tar cf {remote_tar_fname_back} {' '.join(args.copy_backwards)}"
    unpack_command = make_ssh_command(machine_config, remote_tararg)
    subprocess.run(unpack_command)

with tempfile.NamedTemporaryFile(suffix=".tar") as tarfile:
    fname = tarfile.name

    print("transfering files from remote:")
    copy_backward_cmd = make_scp_command_backward(fname, remote_tar_fname_back, machine_config)
    print(" ".join(copy_backward_cmd))
    subprocess.run(copy_backward_cmd)

    print("cleaning up remote:")
    cleanup_command_base = f"rm -r {run_folder}; rm {remote_tar_fname_back}"
    cleanup_command = make_ssh_command(machine_config, cleanup_command_base)
    subprocess.run(cleanup_command)

    print("unpacking local:")
    run_folder = job_result_folder
    tararg = f"mkdir -p {run_folder} && cd {run_folder} && tar xf {fname}"
    print(tararg)
    subprocess.run(tararg,shell=True)
