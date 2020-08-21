import numpy as np

def dict_to_list(names, caps):
    return np.array([caps[name] for name in names],dtype=np.int32)

def gen_schedual_data(machine_caps, proc_deps, proc_weights, proc_times):
    names = list(machine_caps.keys())

    proc_weights = np.asarray(proc_weights)
    proc_times = np.asarray(proc_times)
    mac_caps = dict_to_list(names, machine_caps)
    proc_deps = [dict_to_list(names, proc_dep) for proc_dep in proc_deps]
    idxs = filter_procs(mac_caps, proc_deps, proc_weights, proc_times)
    mac_caps = mac_caps[idxs]

def generate_schedual(machine_caps, proc_deps, proc_weights, proc_times):
    proc_values = (proc_weights) / proc_times

    n_mach = len(machine_caps)
    n_procs = len(proc_deps)
    n_deps = len(machine_caps[0])

    def fitness(individs):
        mac_alloc = individ.reshape((n_mach, n_procs))

        proc_res = mac_alloc.reshape(n_mach, n_procs, 1) * proc_deps.reshape(n_procs, n_deps)
        mac_useage = np.sum(proc_res,axis=1)
        mac_overflow = np.sum(machine_caps.less(mac_useage).astype(np.int32))
        if mac_overflow > 0:
            return -mac_overflow * 10000

        proc_sums = np.sum(mac_alloc,axis=0)
        proc_repeat_cost = -np.sum((proc_sums > 1).astype(np.int32))

        proc_presense = (proc_sums != 0).astype(np.float32)
        proc_vals = np.sum(proc_presense * proc_vals)

        return proc_repeat_cost + proc_vals

def get_under_cap(caps, proc_deps):
    cur_caps = np.zeros_like(caps)
    max_cap = caps * 3
    for i in range(proc_deps):
        cur_cap += proc_deps[i]
        if np.any(cur_cap, max_cap):
            break
    return np.arange(0,i+1)

def filter_procs(machine_caps, proc_deps, proc_weights, proc_times):
    proc_values = (proc_weights) / (1+proc_times)

    best_proc_list = np.argsort(-proc_values)

    proc_deps = proc_deps[best_proc_list]

    tot_mac_caps = np.sum(machine_caps, axis=0)

    all_ordss = get_under_cap(machine_caps, proc_deps)
    all_idxs = best_proc_list[all_ordss]

    return all_idxs
