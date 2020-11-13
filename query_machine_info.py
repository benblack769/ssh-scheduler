import json
def get_cpu_usage():
    '''
    top -n1 -b -i
    '''
    return f"top -n1 -b -i"

def parse_cpu_usage(usage_str):
    '''
    example output:
    top - 15:30:00 up 51 days, 20:03,  4 users,  load average: 1.06, 1.02, 1.00
    Tasks: 285 total,   2 running, 218 sleeping,   0 stopped,   0 zombie
    %Cpu(s): 25.8 us,  2.0 sy,  0.0 ni, 72.1 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st
    KiB Mem : 16353512 total, 11519076 free,  3352228 used,  1482208 buff/cache
    KiB Swap:  4194300 total,  2561836 free,  1632464 used. 12647468 avail Mem

      PID USER      PR  NI    VIRT    RES    SHR S  %CPU %MEM     TIME+ COMMAND
    16635 ben       20   0 20.265g 3.144g 508932 R 106.7 20.2 496:57.22 python
    '''
    print(usage_str)
    cpu, mem = usage_str.strip().split("\n")[2:4]
    cpu_usage = float(cpu.split()[1])
    mem_free = int(mem.split(",")[1].strip().split()[0])
    return {"cpu_usage": cpu_usage, "mem_free": mem_free}

def get_gpu_info():
    '''
    nvidia-smi --query-gpu=name,memory.total,memory.free,memory.used --format=csv
    '''
    return "nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv"

def parse_gpu_info(gpu_info_str):
    '''
    name, memory.total [MiB], memory.free [MiB]
    GeForce GTX 1080 Ti, 11178 MiB, 10403 MiB
    GeForce GTX 1080 Ti, 11176 MiB, 3551 MiB
    '''
    if not gpu_info_str.strip():
        return {"gpus": []}
    else:
        print(gpu_info_str)
        gpus = gpu_info_str.strip().split("\n")[1:]
        gpu_infos = []
        for i, gpu_line in enumerate(gpus):
            name, mem, free = gpu_line.split(",")
            num_free = int(free.strip().split()[0])
            num_mem = int(mem.strip().split()[0])
            gpu_infos.append({
                "name": name,
                "mem": num_mem,
                "free": num_free,
            })

        return {"gpus": gpu_infos}

def get_full_command():
    return f"{get_cpu_usage()} && printf \"<<>>\" && {get_gpu_info()}"

def parse_full_output(out_str):
    beg = out_str.find("<<>>")
    cpu_data = out_str[:beg]
    gpu_data = out_str[beg+5:]
    cpu_entries = parse_cpu_usage(cpu_data)
    gpu_entries = parse_gpu_info(gpu_data)
    return {**cpu_entries, **gpu_entries}

if __name__ == "__main__":
    # test
    import subprocess
    out = subprocess.run(get_full_command(),shell=True,stdout=subprocess.PIPE)
    parsed = parse_full_output(out.stdout.decode("utf-8"))
    print(parsed)
