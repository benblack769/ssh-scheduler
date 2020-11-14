import json
def get_cpu_usage():
    '''
    top
    -n1     # one iteration
    -b      # machine readable mode
    -i      # ignore inactive processes
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
    cpu, mem, swap = usage_str.strip().split("\n")[2:5]
    cpu_usage = float(cpu.split()[1])/100
    mem_entry = swap.split(".")[1].strip().split()[0]
    if "+" in mem_entry:
        mem_entry = int(mem_entry.split("+")[0])*10
    else:
        mem_entry = int(mem_entry)#.split("+")[0]*10
    mem_free = mem_entry//1024
    print(mem_free)
    return {"cpu_usage": cpu_usage, "mem_free": mem_free}

def get_cpu_count():
    return "lscpu"

def parse_cpu_count(usage_str):
    lines = usage_str.split("\n")
    cpu_count = 16 # default 16
    for line in lines:
        if "CPU(s):" in line:
            cpu_count = int(line.strip().split()[1])
            break
    return {"cpu_count": cpu_count}

def get_gpu_info():
    '''
    from https://nvidia.custhelp.com/app/answers/detail/a_id/3751/~/useful-nvidia-smi-queries
    '''
    return "nvidia-smi --query-gpu=name,memory.total,memory.free,utilization.gpu --format=csv"

def parse_gpu_info(gpu_info_str):
    '''
    name, memory.total [MiB], memory.free [MiB], utilization.gpu [%]
    GeForce GTX 1080 Ti, 11178 MiB, 10403 MiB, 25 %
    GeForce GTX 1080 Ti, 11176 MiB, 3551 MiB, 28 %
    '''
    if not gpu_info_str.strip():
        return {"gpus": []}
    else:
        gpus = gpu_info_str.strip().split("\n")[1:]
        gpu_infos = []
        for i, gpu_line in enumerate(gpus):
            name, mem, free, util = gpu_line.split(",")
            num_free = int(free.strip().split()[0])
            num_mem = int(mem.strip().split()[0])
            utilization = float(util.strip().split()[0])/100
            gpu_infos.append({
                "name": name,
                "mem": num_mem,
                "free": num_free,
                "utilization": utilization,
            })

        return {"gpus": gpu_infos}

def get_full_command():
    return f"{get_cpu_usage()} && printf \"<<>>\" && {get_cpu_count()} && printf \"<<>>\" &&{get_gpu_info()}"

def parse_full_output(out_str):
    beg = out_str.find("<<>>")
    mid = out_str.rfind("<<>>")
    cpu_data = out_str[:beg]
    cpu_count_data = out_str[beg+5:mid]
    gpu_data = out_str[mid+5:]
    cpu_entries = parse_cpu_usage(cpu_data)
    gpu_entries = parse_gpu_info(gpu_data)
    cpu_count_entries = parse_cpu_count(cpu_count_data)
    return {**cpu_entries, **cpu_count_entries, **gpu_entries}

if __name__ == "__main__":
    # test
    import subprocess
    out = subprocess.run(get_full_command(),shell=True,stdout=subprocess.PIPE)
    parsed = parse_full_output(out.stdout.decode("utf-8"))
    print(json.dumps(parsed))
