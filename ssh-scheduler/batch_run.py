#!/usr/bin/python3
import argparse
import tempfile
import yaml
import json
import subprocess
import base64
import re
import sys
import time
import shlex
import copy
import os
import signal
from ssh_scheduler import better_basic_run
from ssh_scheduler.query_machine_info import get_full_command, parse_full_output
from .machine_cost_model import machine_cost, is_over_limit, get_process_gpu_limit, get_best_gpu, get_best_machine, init_machine_limit, add_to_machine_state, remove_from_machine_state
from .better_basic_run import generate_command


my_folder = os.path.dirname(os.path.realpath(__file__))


def run_all(commands):
    procs = []
    for command in commands:
        proc = subprocess.Popen(command,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        procs.append(proc)
    outputs = []
    for proc in procs:
        out, err = proc.communicate()
        print(err,file=sys.stderr)
        if proc.returncode != 0:
            print(out,file=sys.stderr)
            out = None
        else:
            out = out.decode("utf-8")
        outputs.append(out)
    return outputs


def find_all_machine_info(machines):
    cmd = get_full_command()
    commands = [better_basic_run.make_ssh_command(mac, cmd) for mac in machines]
    outputs = run_all(commands)
    if not all(outputs):
        fail_machines = [(mach, " ".join(cmd)) for out,mach,cmd in zip(outputs, machines, commands) if out is None]
        raise RuntimeError("could not connect to machines: "+json.dumps(fail_machines))
    parsed_outs = [parse_full_output(out) for out in outputs]
    for out in parsed_outs:
        init_machine_limit(out)
    return parsed_outs


def make_basic_run_command(machine, job_name, export_prefix, command, gpu_choice, args):
    stdout = open(f"./job_results/{job_name}.out",'a',buffering=1)
    stderr = open(f"./job_results/{job_name}.err",'a',buffering=1)
    proc = generate_command(
        args.copy_forwards,
        args.copy_backwards,
        machine,
        job_name,
        args.verbose,
        command,
        stdout=stdout,
        stderr=stderr
    )
    return proc


def make_ssh_scheduler_run_command(machine, job_name, export_prefix, command, gpu_choice, args):
    # add required args for parsing
    final_command = command
    if "--copy-forward" not in command:
        final_command += f" --copy-forward {' '.join(args.copy_forward)} "
    if "--copy-backwards" not in command:
        final_command += f" --copy-backwards {' '.join(args.copy_backwards)} "
    if "--job-name" not in command:
        final_command += f" --job-name {job_name} "
    if args.verbose:
        final_command += f" --verbose "
    final_command += f" --machine {machine} "

    split_cmd = shlex.split(final_command)[1:]
    parse_results = better_basic_run.parse_args(split_cmd)
    # final_command = final_command.replace(parse_results.command, f" {export_prefix} {parse_results.command} ")
    # catted_cmd =  f" {export_prefix} {parse_results.command} "
    run_proc = make_basic_run_command(machine, parse_results.job_name, export_prefix, parse_results.command, gpu_choice, parse_results)

    return run_proc, parse_results.job_name


def main():
    parser = argparse.ArgumentParser(
        description='Run a batched command',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--copy-forwards', nargs='*', default=[], help='Files and folders to copy when running the command. Defaults to everything in the current working directory')
    parser.add_argument('--copy-backwards', nargs='*', default=[], help='Files and folders to copy back from the worker running the command. Defaults to everything in the current working directory')
    parser.add_argument('--machines', nargs='*', help='machine id', required=True)
    parser.add_argument('--num-cpus', type=int, default=1, help='cpus to reserve for the job')
    parser.add_argument('--memory-required', type=int, default=7000, help='memory to reserve for the job')
    parser.add_argument('--reserve', action="store_true", help='reserve entire machine for job')
    parser.add_argument('--no-reserve-gpu', action="store_true", help='reserve entire machine for job')
    parser.add_argument('--no-gpu-required', action="store_true", help='is a gpu required for the job')
    parser.add_argument('--gpu-memory-required', type=int, default=1000, help='gpu memory to reserve for the job')
    parser.add_argument('--gpu-utilization', type=float, default=0.75, help='gpu utilization consumed')
    parser.add_argument('--verbose', action="store_true", help='print out debug information')
    parser.add_argument('--dry-run', action="store_true", help='just print out first round of commands')
    parser.add_argument('--commands', action="store_true", help='Whether the batch file should be interpreted as ssh_scheduler commands instead of bash commands')
    parser.add_argument('filename', help="a file where each line contains a command")

    args = parser.parse_args()

    lines = open(args.filename).readlines()
    machine_configs = [better_basic_run.load_data_from_yaml(mac) for mac in args.machines]
    machine_infos = find_all_machine_info(machine_configs)
    machine_gpu_choices = [get_process_gpu_limit(info, args) for info in machine_infos]
    machine_proc_limits = [len(c) for c in machine_gpu_choices]
    print("machine limits: ", {name:limit for name, limit in zip(args.machines,machine_proc_limits)})
    print("machine gpu choices:",machine_gpu_choices)
    machine_procs = [[None for i in range(limit)] for limit in machine_proc_limits]
    save_filename = args.filename.replace("/","_")
    job_names = [f"{save_filename}.{line_num+1}" for line_num in range(len(lines))]
    for line_num in range(len(lines)):
        if os.path.exists(f"./job_results/{job_names[line_num]}"):
            print(f"WARNING: job results already exists for line {line_num+1}, skipping evaluation: delete if you wish to rerun")

    def poll_all_jobs():
        not_finished_procs = []
        for p_line_num, p_machine, p_gpu, proc in proc_list:
            if args.dry_run or proc.poll() is not None:
                message = "finished" if args.dry_run or proc.returncode == 0 else "failed"
                job_name = job_names[p_line_num]
                machine_infos[p_machine] = remove_from_machine_state(machine_infos[p_machine], p_gpu)
                print(f"{message}: {job_name}; {lines[p_line_num].strip()}",flush=True)
            else:
                not_finished_procs.append((p_line_num, p_machine, p_gpu, proc))
        proc_list[:] = not_finished_procs

    proc_list = []
    machine_config = args
    os.makedirs("./job_results/",exist_ok=True)
    for line_num in range(len(job_names)):
        job_name = job_names[line_num]
        if os.path.exists(f"./job_results/{job_name}"):
            print("skipping", lines[line_num].strip(),flush=True)
            continue
        not_polled = True
        while not_polled or is_over_limit(machine_cost(machine_config, machine_infos[best_machine_idx])):
            if not not_polled:
                if not args.dry_run:
                    # ssh commands take at least a second to finish
                    # so its a reasonable slow-query time
                    time.sleep(1)

                # revert machine addition from previous loop iteration
                machine_infos[best_machine_idx] = remove_from_machine_state(machine_infos[best_machine_idx], best_gpu_idx)

                poll_all_jobs()

            not_polled = False

            best_machine_idx = get_best_machine(machine_infos, machine_config)
            best_gpu_idx = get_best_gpu(machine_config, machine_infos[best_machine_idx])
            machine_infos[best_machine_idx] = add_to_machine_state(machine_infos[best_machine_idx], machine_config, best_gpu_idx)


        # start new job
        command = lines[line_num].strip()
        export_prefix = f"export CUDA_VISIBLE_DEVICES={best_gpu_idx} &&" if not args.reserve and not args.no_gpu_required else ""
        machine = machine_configs[best_machine_idx]
        job_name = job_names[line_num]
        if not args.dry_run:
            if args.commands:
                proc, new_job_name = make_ssh_scheduler_run_command(machine, job_name, export_prefix, command, best_gpu_idx, args)
                job_name = job_names[line_num] = new_job_name
            else:
                proc = make_basic_run_command(machine, job_name, export_prefix, command, best_gpu_idx, args)
        else:
            proc = None

        proc_list.append((
            line_num,
            best_machine_idx,
            best_gpu_idx,
            proc
        ))

        print(f"started: {job_name};  {command}",flush=True)
        if not args.dry_run:
            # give time as to not overload the sshd server
            time.sleep(0.1)
    while proc_list:
        poll_all_jobs()
        if not args.dry_run:
            time.sleep(1)


if __name__ == "__main__":
    main()
