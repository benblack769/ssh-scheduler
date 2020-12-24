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

def make_ssh_command(machine_config, command, open_terminal=False):
    ssh_command = f"ssh -T -o StrictHostKeyChecking=no -o ConnectTimeout=5 -p {machine_config['port']} -i {machine_config['ssh_key_path']} {machine_config['username']}@{machine_config['ip']}"
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

    def vprint(*fargs):
        if args.verbose:
            print(*fargs)

    job_name = rand_fname() if args.job_name == "__random__" else args.job_name
    job_result_folder = os.path.expanduser("./job_results/")+job_name
    if os.path.exists(job_result_folder):
        raise RuntimeError(f"results for job '{job_name}' already exist, move or remove files before continuing")

    run_folder = "job_data/"+job_name
    remote_tar_fname = "/tmp/"+rand_fname(".tar")
    remote_tar_fname_back = "/tmp/"+rand_fname(".tar")

    with tempfile.NamedTemporaryFile(suffix=".tar") as tarfile:
        with tempfile.NamedTemporaryFile(dir=".",suffix=".sh") as script_file:
            script_name = os.path.basename(script_file.name)
            script_contents = f'{args.command} &\n'
            script_contents += "disown\n"
            script_contents += "echo $!\n"
            script_contents += "wait\n"
            script_contents += f"cd && cd {run_folder} && tar cfm {remote_tar_fname_back} {' '.join(args.copy_backwards)}\n"
            print("".join(script_contents))
            script_file.write(script_contents.encode("utf-8"))
            script_file.flush()

            fname = tarfile.name

            vprint("preparing files for transfer:")
            tararg = f"tar --exclude job_results --exclude .git -cmf {fname} {' '.join(args.copy_forward)} {script_name}"
            vprint(tararg)
            subprocess.run(tararg,shell=True)

        vprint("transfering files to remote:")
        copy_forward_cmd = make_scp_command_forward(fname, remote_tar_fname, machine_config)
        vprint(" ".join(copy_forward_cmd))
        subprocess.run(copy_forward_cmd)

    try:
        vprint("running command on remote:")
        setup_data = f"mkdir -p {run_folder} && cd {run_folder} && tar xfm {remote_tar_fname} && rm {remote_tar_fname} "
        interactive_command = f"{setup_data} && stdbuf -i0 -o0 -e0  bash -i {script_name}"
        run_command = make_ssh_command(machine_config, interactive_command)
        vprint(" ".join(run_command))
        proc = subprocess.Popen(run_command, stdout=subprocess.PIPE)
        line = proc.stdout.readline()
        pid = int(line.strip())
        line = proc.stdout.readline()
        while line:
            print(line)
            line = proc.stdout.readline()

        proc.wait()
        returncode = proc.returncode
    except KeyboardInterrupt:
        print("killing job on remote (KeyboardInterrupt):")
        run_command = make_ssh_command(machine_config, f"kill {pid}")
        print(run_command,flush=True)
        main_cmd = subprocess.run(run_command)
        proc.wait()
        print("finished transfering files",flush=True)
        returncode = 1

    with tempfile.NamedTemporaryFile(suffix=".tar") as tarfile:
        fname = tarfile.name

        vprint("transfering files from remote:")
        copy_backward_cmd = make_scp_command_backward(fname, remote_tar_fname_back, machine_config)
        vprint(" ".join(copy_backward_cmd))
        subprocess.run(copy_backward_cmd)

        vprint("cleaning up remote:")
        cleanup_command_base = f"rm -rf {run_folder}; rm {remote_tar_fname_back}"
        cleanup_command = make_ssh_command(machine_config, cleanup_command_base)
        subprocess.run(cleanup_command)

        vprint("unpacking local:")
        run_folder = job_result_folder
        tararg = f"mkdir -p {run_folder} && cd {run_folder} && tar xfm {fname}"
        vprint(tararg)
        subprocess.run(tararg,shell=True)

    exit(returncode)


if __name__ == "__main__":
    main()
