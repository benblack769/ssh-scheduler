#!/usr/bin/python3
import argparse
import tempfile
import yaml
import json
import subprocess
import base64
import os

yaml_path = os.path.expanduser("~/.local/var/")

def load_data_from_yaml(computer_override):
    global_path = os.path.join(yaml_path,"{}".format(computer_override))
    if os.path.exists(computer_override):
        machine_path = computer_override
    elif os.path.exists(computer_override+".yaml"):
        machine_path = computer_override+".yaml"
    elif os.path.exists(global_path):
        machine_path = global_path
    elif os.path.exists(global_path+".yaml"):
        machine_path = global_path+".yaml"
    else:
        raise RuntimeError(f"Machine config not found at {yaml_path}{computer_override}.yaml or at {computer_override}.yaml. Please define a correct config")
    machine_data = yaml.safe_load(open(machine_path))
    return machine_data

def rand_fname(suffix=""):
    return base64.b16encode(os.urandom(12)).decode("utf-8") + suffix

def make_scp_command_forward(source_file, dest_file, machine_config):
    return f"scp -P {machine_config['port']} -i {machine_config['ssh_key_path']} {source_file} {machine_config['username']}@{machine_config['ip']}:{dest_file}".split(" ")

def make_scp_command_backward(source_file, dest_file, machine_config):
    return f"scp -P {machine_config['port']} -i {machine_config['ssh_key_path']} {machine_config['username']}@{machine_config['ip']}:{dest_file} {source_file}".split(" ")

def make_interactive_command(command):
    command = f'echo {json.dumps(command)} | stdbuf -i0 -o0 -e0  bash -i '
    return command

def make_ssh_command(machine_config, command, open_terminal=False):
    ssh_command = f"ssh -T -o StrictHostKeyChecking=no -o ConnectTimeout=5 -p {machine_config['port']} -i {machine_config['ssh_key_path']} {machine_config['username']}@{machine_config['ip']}"
    print(f"{ssh_command} '{command}'")
    final_command = ssh_command.split(" ") + [command]
    return final_command

def main():
    parser = argparse.ArgumentParser(description='Run a simple command')
    parser.add_argument('--copy-forward', nargs='*', default=[], help='Folders to copy when running the command. Defaults to everything in the current working directory')
    parser.add_argument('--copy-backwards', nargs='*', default=[], help='Files and folders to copy back from the worker running the command. Defaults to everything in the current working directory')
    parser.add_argument('--machine', help='machine id', required=True)
    parser.add_argument('--job-name', default="__random__", help='job name')
    parser.add_argument('--verbose', action="store_true", help='print debugging information to stderr')
    parser.add_argument('command')

    args = parser.parse_args()

    machine_config = load_data_from_yaml(args.machine)

    job_name = rand_fname() if args.job_name == "__random__" else args.job_name
    job_result_folder = os.path.expanduser("./job_results/")+job_name
    if os.path.exists(job_result_folder):
        raise RuntimeError(f"results for job '{job_name}' already exist, move or remove files before continuing")

    with tempfile.NamedTemporaryFile(suffix=".tar") as tarfile:
        fname = tarfile.name

        print("preparing files for transfer:")
        tararg = f"tar --exclude job_results --exclude .git -cmf {fname} {' '.join(args.copy_forward)}"
        print(tararg)
        subprocess.run(tararg,shell=True)

        print("transfering files to remote:")
        remote_tar_fname = "/tmp/"+rand_fname(".tar")
        copy_forward_cmd = make_scp_command_forward(fname, remote_tar_fname, machine_config)
        print(" ".join(copy_forward_cmd))
        subprocess.run(copy_forward_cmd)

    if True:
        run_folder = "job_data/"+job_name

        print("unpacking files on remote:")
        unpack_base = f"mkdir -p {run_folder} && cd {run_folder} && tar xfm {remote_tar_fname} && rm {remote_tar_fname}"
        unpack_command = make_ssh_command(machine_config, unpack_base)
        subprocess.run(unpack_command)

    try:
        print("running command:")
        base_run_command = f"cd {run_folder} && " + (args.command)
        interactive_command = make_interactive_command(base_run_command)
        run_command = make_ssh_command(machine_config, interactive_command)#, open_terminal=True)
        main_cmd = subprocess.run(run_command)
        returncode = main_cmd.returncode
    except:
        returncode = 1

    if True:
        print("collecting data on remote:")
        remote_tar_fname_back = "/tmp/"+rand_fname(".tar")
        remote_tararg = f"cd {run_folder} && tar cfm {remote_tar_fname_back} {' '.join(args.copy_backwards)}"
        unpack_command = make_ssh_command(machine_config, remote_tararg)
        subprocess.run(unpack_command)

    with tempfile.NamedTemporaryFile(suffix=".tar") as tarfile:
        fname = tarfile.name

        print("transfering files from remote:")
        copy_backward_cmd = make_scp_command_backward(fname, remote_tar_fname_back, machine_config)
        print(" ".join(copy_backward_cmd))
        subprocess.run(copy_backward_cmd)

        print("cleaning up remote:")
        cleanup_command_base = f"rm -rf {run_folder}; rm {remote_tar_fname_back}"
        cleanup_command = make_ssh_command(machine_config, cleanup_command_base)
        subprocess.run(cleanup_command)

        print("unpacking local:")
        run_folder = job_result_folder
        tararg = f"mkdir -p {run_folder} && cd {run_folder} && tar xfm {fname}"
        print(tararg)
        subprocess.run(tararg,shell=True)

    exit(returncode)


if __name__ == "__main__":
    main()
