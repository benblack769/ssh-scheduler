#!/usr/bin/python3
import argparse
import tempfile
import yaml
import json
import subprocess
import base64
import os
import sys
import signal
import shlex
import time
import random


def parse_args(args_list):
    parser = argparse.ArgumentParser(description='Run a simple command')
    parser.add_argument('--copy-forwards', nargs='*', default=[], help='Folders to copy when running the command. Defaults to everything in the current working directory')
    parser.add_argument('--copy-backwards', nargs='*', default=[], help='Files and folders to copy back from the worker running the command. Defaults to everything in the current working directory')
    parser.add_argument('--machine', help='machine id', required=True)
    parser.add_argument('--job-name', default="__random__", help='job name')
    parser.add_argument('--verbose', action="store_true", help='print debugging information to stderr')
    parser.add_argument('command')

    return parser.parse_args(args_list)


def load_data_from_yaml(computer_override):
    yaml_path = os.path.expanduser("~/.local/var/")
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


def make_ssh_command(machine_config, command):
    ssh_command = f"ssh -T -o StrictHostKeyChecking=no -o ConnectTimeout=5 -p {machine_config['port']} -i {machine_config['ssh_key_path']} {machine_config['username']}@{machine_config['ip']} '{command}'"
    return ssh_command


def rand_fname(suffix=""):
    return base64.b16encode(os.urandom(12)).decode("utf-8") + suffix


def printe(*args):
    print(*args, file=sys.stderr)


class CleanupShellProcess:
    def __init__(self, command, cleanups=[], **kwargs):
        self.proc = subprocess.Popen(command, shell=True, **kwargs)
        self.cleanups = cleanups

    def close(self):
        for cleanup in self.cleanups:
            subprocess.Popen(cleanup, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def wait(self):
        self.proc.wait()

    def communicate(self):
        out, err = self.proc.communicate()
        return out, err

    def __enter__(self):
        return self.proc

    def __exit__(self, type, value, traceback):
        self.close()

    def __del__(self):
        self.close()


def generate_command(
    copy_forwards,
    copy_backwards,
    machine_config,
    job_name,
    verbose,
    command,
    stdout=None,
    stderr=None
):

    def vprint(*fargs):
        if verbose:
            printe(*fargs)

    job_name = rand_fname() if job_name == "__random__" else job_name
    job_result_folder = os.path.expanduser("./job_results/")+job_name
    if copy_backwards and os.path.exists(job_result_folder):
        raise RuntimeError(f"results for job '{job_name}' already exist, move or remove files before continuing")

    run_folder = "job_data/"+job_name
    local_data_folder = "job_results/"+job_name
    pid_name = "."+rand_fname("_pid.txt")
    stdout_separator = rand_fname()
    script_name = "tmp/"+rand_fname(".sh")
    local_script_file = "/"+script_name
    local_all_out_file = "/tmp/"+rand_fname()

    script_contents = rf'{command} &\n'
    script_contents += r"RETVAL=$!\n"
    script_contents += rf"echo $RETVAL > {pid_name}\n"
    script_contents += rf"echo  started command $RETVAL ...  >&2 \n"
    script_contents += r"wait $RETVAL\n"
    script_contents += r"RETCODE=$?\n"
    script_contents += r"exit $RETCODE\n"


    create_local_script = f"printf '{script_contents}' > {local_script_file}"

    # gather_results_command = f"cd && cd {run_folder} && tar cfm {remote_tar_fname_back} {' '.join(.copy_backwards)}\n"
    q = '"'
    vprint(f"Script contents:\n{eval(q+script_contents+q)}")
    tararg = f"tar --exclude job_results --exclude .git -cmf - {' '.join(copy_forwards)} {local_script_file}"
    setup_data = f"(rm -rf {run_folder} && mkdir -p {run_folder} && cd {run_folder} && tar -x ) "
    # quoted_command = shlex.quote(.command)
    # vprint(quoted_command)
    return_results_command = f"tar -cmf - {' '.join(copy_backwards)}"
    interactive_command = f"stdbuf -i0 -o0 -e0  bash -i {script_name}"
    full_remote_command = f"{setup_data} && cd {run_folder} && {interactive_command} ; echo {stdout_separator} ; {return_results_command}"

    remote_kill_cleanup = f"kill -- $(cat {os.path.join(run_folder,pid_name)})"
    remote_wait_cleaup = f"sleep 0.3" # wait for kill to finalize...
    remote_file_cleanup = f"rm -rf {run_folder}"
    full_remote_cleanup = f"{remote_kill_cleanup} && {remote_wait_cleaup} ; {remote_file_cleanup}"
    ssh_remote_cleanup = make_ssh_command(machine_config, full_remote_cleanup)

    get_stdout_txt = f"sed -n '/{stdout_separator}/q;p'"
    divert_all_data = f"tee {local_all_out_file}"
    remove_stdout = f"sed -n '/{stdout_separator}/,$p' {local_all_out_file} | tail -n +2 | tar xm "
    unpack_tar_out = f"( mkdir -p {local_data_folder} && cd {local_data_folder} && {remove_stdout} ) " if copy_backwards else ' : '
    post_process_output = f"{divert_all_data} | {get_stdout_txt}"

    cleanup_local_files = f"rm -f {local_all_out_file} {local_script_file}"
    cleanup_remote_delay = f"sleep {random.random()*2}" # keeps number of ssh connections at once to a reasonable number
    cleanup_remote_safe = f"{cleanup_remote_delay} ; {ssh_remote_cleanup}"
    cleanup_local_safe = f"{unpack_tar_out}; {cleanup_local_files}"

    full_command = f"{create_local_script} && {tararg} | {make_ssh_command(machine_config, full_remote_command)} | {post_process_output}"

    vprint(full_command)

    safeproc = CleanupShellProcess(full_command, cleanups=[cleanup_remote_safe, cleanup_local_safe], stdout=stdout, stderr=stderr)
    return safeproc


def main():
    args = parse_args(sys.argv[1:])

    machine_config = load_data_from_yaml(args.machine)
    proc = generate_command(
        args.copy_forwards,
        args.copy_backwards,
        machine_config,
        args.job_name,
        args.verbose,
        args.command
    )
    proc.wait()


if __name__ == "__main__":
    main()
