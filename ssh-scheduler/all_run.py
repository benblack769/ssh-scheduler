import os
import subprocess
import argparse
import subprocess
from better_basic_run import generate_command, load_data_from_yaml


my_folder = os.path.dirname(os.path.realpath(__file__))


def main():
    parser = argparse.ArgumentParser(description='Run a simple command')
    parser.add_argument('--copy-forwards', nargs='*', default=[], help='Folders to copy when running the command. Defaults to everything in the current working directory')
    parser.add_argument('--copy-backwards', nargs='*', default=[], help='Files and folders to copy back from the worker running the command. Defaults to everything in the current working directory')
    parser.add_argument('--machines', nargs='*', help='machine id', required=True)
    parser.add_argument('--job-name', default="__random__", help='job name')
    parser.add_argument('--verbose', action="store_true", help='print debugging information to stderr')
    parser.add_argument('command')

    args = parser.parse_args()

    procs = []
    for i,machine in enumerate(args.machines):
        job_name = "__random__" if args.job_name == "__random__" else f"{args.job_name}_{i}"
        machine_config = load_data_from_yaml(machine)
        procs.append(generate_command(
            args.copy_forwards,
            args.copy_backwards,
            machine_config,
            job_name,
            args.verbose,
            args.command,
            stdout=None,
            stderr=None
        ))
    for proc in procs:
        proc.communicate()


if __name__ == "__main__":
    main()
