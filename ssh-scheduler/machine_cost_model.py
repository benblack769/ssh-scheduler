import copy


MAX_COST = 1e10


def is_over_limit(cost):
    return cost >= MAX_COST


def gpu_cost(machine_config, gpu_state):
    MAX_UTILIZATION = 1.2
    return (
        (MAX_COST if gpu_state['free'] < 0 else 0) +
        (MAX_COST if gpu_state['reserved'] > 1 else 0) +
        MAX_COST * ((gpu_state['utilization']/MAX_UTILIZATION) ** 3)
    )

def argmin(costs):
    return min((cost, i) for i, cost in enumerate(costs))[1]


def get_best_gpu(machine_config, machine_state):
    if 'gpus' not in machine_state:
        return None
    return argmin(gpu_cost(machine_config, gpu_conf) for gpu_conf in machine_state['gpus'])

def get_best_machine(machine_states, machine_config):
    return argmin(machine_cost(machine_config, machine_state) for machine_state in machine_states)


def machine_cost(machine_config, machine_state):
    MAX_CPU_UTILIZATION = 1.5
    min_gpu_cost = 0
    if not machine_config.no_gpu_required:
        min_gpu_cost = min(gpu_cost(machine_config, gpu_conf) for gpu_conf in machine_state['gpus'])
    return (
        (MAX_COST if machine_state['reserved'] > 1 else 0) +
        (MAX_COST if machine_state['mem_free'] < 0 else 0) +
        MAX_COST * ((machine_state['cpu_usage']/MAX_CPU_UTILIZATION) ** 3) +
        min_gpu_cost
    )


def add_to_gpu_state(old_gpu_state, machine_config):
    """return copy of gpu state with new job instance added"""
    gpu_state = copy.copy(old_gpu_state)
    gpu_state['old_state'] = old_gpu_state

    gpu_state['free'] -= machine_config.gpu_memory_required
    gpu_state['utilization'] += machine_config.gpu_utilization
    if not machine_config.no_reserve_gpu:
        gpu_state['reserved'] += 1
    return gpu_state


def add_to_machine_state(old_machine_state, machine_config, gpu_idx):
    """return shallow copy of machine state with new job instance added"""
    machine_state = copy.copy(old_machine_state)
    machine_state['old_state'] = old_machine_state
    if machine_config.reserve:
        machine_state['reserved'] += 1
    machine_state['cpu_usage'] += machine_config.num_cpus / machine_state['cpu_count']
    machine_state['mem_free'] -= machine_config.memory_required
    if not machine_config.no_gpu_required:
        machine_state['gpus'][gpu_idx] = add_to_gpu_state(machine_state['gpus'][gpu_idx], machine_config)

    return machine_state


def remove_from_machine_state(old_machine_state, gpu_idx):
    machine_state = old_machine_state['old_state']
    assert machine_state['gpus'] is old_machine_state['gpus'], "don't copy gpu list"
    machine_state['gpus'][gpu_idx] = old_machine_state['gpus'][gpu_idx]['old_state']
    return machine_state


def init_machine_limit(machine_limit):
    """
    machine limit comes from query_machine_info
    """
    machine_limit['reserved'] = 0
    for gpu in machine_limit['gpus']:
        gpu['reserved'] = 0


def get_process_gpu_limit(machine_limit, machine_config):
    '''
    machine limit looks like this:
    {"cpu_usage": 0.124, "mem_free": 30607, "cpu_count": 24, "gpus": [{"name": "GeForce RTX 2060", "mem": 5934, "free": 5933, "utilization": 0.0}, {"name": "GeForce RTX 2060", "mem": 5932, "free": 5931, "utilization": 0.0}]}
    '''
    machine_limit = copy.deepcopy(machine_limit)

    if not machine_limit['gpus'] and not machine_config.no_gpu_required:
        return []

    init_machine_limit(machine_limit)

    gpu_choices = []
    while True:
        best_gpu = get_best_gpu(machine_config, machine_limit)
        machine_limit = add_to_machine_state(machine_limit, machine_config, best_gpu)
        cost = machine_cost(machine_config, machine_limit)
        if is_over_limit(cost):
            break
        gpu_choices.append(best_gpu)
    return gpu_choices
