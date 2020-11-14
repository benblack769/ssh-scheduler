#!/usr/bin/python3
import argparse
import tempfile
import yaml
import json
import subprocess
import base64
import sys
import time
import copy
import os
import signal
from ml_scheduler import basic_run
from ml_scheduler.query_machine_info import get_full_command, parse_full_output

def run_all(commands):
    procs = []
    for command in commands:
        proc = subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        procs.append(proc)
    outputs = []
    for proc in procs:
        out, err = proc.communicate()
        print(err,file=sys.stderr)
        if proc.returncode != 0:
            out = None
        else:
            out = out.decode("utf-8")
        outputs.append(out)
    return outputs

def find_all_machine_info(machines):
    cmd = get_full_command()
    commands = [basic_run.make_ssh_command(mac, cmd) for mac in machines]
    outputs = run_all(commands)
    parsed_outs = [parse_full_output(out) for out in outputs]
    return parsed_outs

def machine_limit_over(machine_limit):
    return (machine_limit['reserved'] > 1 or
        machine_limit['cpu_usage'] > 200 or
        machine_limit['mem_free'] < 0 or
        any(gpu['free'] < 0 for gpu in machine_limit['gpus']) or
        any(gpu['reserved'] > 1 for gpu in machine_limit['gpus']))

def subtract_process_req(machine_limit, args):
    if args.reserve:
        machine_limit['reserve'] += 1
    NUM_CPUS_ASSUMED = 16  # TODO: replace with actual CPU count (need to get in query_machine_info.py)
    machine_limit['cpu_usage'] += args.num_cpus/NUM_CPUS_ASSUMED
    machine_limit['mem_free'] -= args.memory_required
    gpu_idx = 0
    if not args.no_gpu_required:
        gpu_choice = None
        for i,gpu in enumerate(machine_limit['gpus']):
            if gpu_choice is None or gpu_choice['reserved'] or gpu_choice['free'] < gpu['free']:
                gpu_choice = gpu
                gpu_idx = i
        gpu_choice['free'] -= args.gpu_memory_required
        if not args.no_reserve_gpu:
            gpu_choice['reserved'] += 1
    return gpu_idx

def init_machine_limit(machine_limit):
    machine_limit['reserved'] = 0
    for gpu in machine_limit['gpus']:
        gpu['reserved'] = 0

def get_process_limit(machine_limit, args):
    '''
    machine limit looks like this:
    {"cpu_usage": 25.8, "mem_free": 11486128, "gpus": [{"name": "GeForce GTX 1070", "mem": 8117, "free": 560}]}
    '''
    machine_limit = copy.deepcopy(machine_limit)

    if not machine_limit['gpus'] and not args.no_gpu_required:
        return []

    init_machine_limit(machine_limit)
    gpu_choices = []
    while True:
        gpu_choice = subtract_process_req(machine_limit, args)
        if machine_limit_over(machine_limit):
            break
        gpu_choices.append(gpu_choice)
    return gpu_choices

def make_basic_run_command(machine, job_name, command, gpu_choice, args):
    basic_cmd = f"basic_run.py --copy-forward {' '.join(args.copy_forward)}  --copy-backwards {' '.join(args.copy_backwards)} --machine={machine} --job-name={job_name} {'--verbose' if args.verbose else ''}".split()
    cmd = basic_cmd + [command]
    return cmd

def main():
    parser = argparse.ArgumentParser(description='Run a batched command')
    parser.add_argument('--copy-forward', nargs='*', default=["./"], help='Files and folders to copy when running the command. Defaults to everything in the current working directory')
    parser.add_argument('--copy-backwards', nargs='*', default=["./"], help='Files and folders to copy back from the worker running the command. Defaults to everything in the current working directory')
    parser.add_argument('--machines', nargs='*', default=["local"],help='machine id')
    parser.add_argument('--job-name', default="__random__", help='job name')
    parser.add_argument('--num-cpus', type=int, default=1, help='cpus to reserve for the job')
    parser.add_argument('--memory-required', type=int, default=7000, help='memory to reserve for the job')
    parser.add_argument('--reserve', action="store_true", help='reserve entire machine for job')
    parser.add_argument('--no-reserve-gpu', action="store_true", help='reserve entire machine for job')
    parser.add_argument('--no-gpu-required', action="store_true", help='is a gpu required for the job')
    parser.add_argument('--gpu-memory-required', type=int, default=1000, help='gpu memory to reserve for the job')
    parser.add_argument('--gpu-compute-required', type=int, default=15, help='gpu compute ')
    parser.add_argument('--verbose', action="store_true", help='print out debug information')
    parser.add_argument('--dry-run', action="store_true", help='just print out first round of commands')
    parser.add_argument('filename', help="a file where each line contains a command")

    args = parser.parse_args()

    lines = open(args.filename).readlines()
    machine_configs = [basic_run.load_data_from_yaml(mac) for mac in args.machines]
    machine_infos = find_all_machine_info(machine_configs)
    machine_gpu_choices = [get_process_limit(info, args) for info in machine_infos]
    machine_proc_limits = [len(c) for c in machine_gpu_choices]
    print("machine limits: ", {name:limit for name, limit in zip(args.machines,machine_proc_limits)})
    print("machine gpu choices:",machine_gpu_choices)
    machine_procs = [[None for i in range(limit)] for limit in machine_proc_limits]
    for line_num in range(len(lines)):
        job_name = f"{args.filename}.{line_num+1}"
        if os.path.exists(f"./job_results/{job_name}"):
            print(f"WARNING: job results already exists for line {line_num+1}, skipping evaluation: delete if you wish to rerun")

    os.makedirs("./job_results/",exist_ok=True)
    line_num = 0
    try:
        all_done = False
        while not all_done:
            all_done = True
            for mac,gpu_choices,procs in zip(args.machines, machine_gpu_choices, machine_procs):
                for i,(gpu_choice, proc) in enumerate(zip(gpu_choices, procs)):
                    if proc is not None and proc[1].poll() is not None:
                        print("finished: ",proc[0])
                        proc = procs[i] = None
                    if proc is None and line_num < len(lines):
                        command = f"export CUDA_VISIBLE_DEVICES={gpu_choice} && {lines[line_num].strip()}"
                        job_name = f"{args.filename}.{line_num+1}"
                        if os.path.exists(f"./job_results/{job_name}"):
                            print("skipping", command)
                        else:
                            job_cmd = make_basic_run_command(mac, job_name, command, gpu_choice, args)
                            if args.verbose or args.dry_run:
                                print(" ".join(job_cmd))
                            if not args.dry_run:
                                print("started:", command)
                                stdout_file = open(f"./job_results/{job_name}.out",'a',buffering=1)
                                stderr_file = open(f"./job_results/{job_name}.err",'a',buffering=1)
                                process = subprocess.Popen(job_cmd,stdout=stdout_file, stderr=stderr_file,start_new_session=True)#,creationflags=subprocess.DETACHED_PROCESS)
                                proc = procs[i] = (command, process)
                        line_num += 1
                        all_done = False
                    if proc is not None:
                        all_done = False
            time.sleep(1)
    except BaseException:
        print("interrupting tasks")
        for procs in machine_procs:
            for proc in procs:
                if proc is not None:
                    proc[1].send_signal(signal.SIGINT)
        print("waiting for tasks to terminate")
        for procs in machine_procs:
            for proc in procs:
                if proc is not None:
                    proc[1].wait()


if __name__ == "__main__":
    main()
