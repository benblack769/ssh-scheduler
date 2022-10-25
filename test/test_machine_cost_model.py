import copy
from ssh_scheduler.machine_cost_model import init_machine_limit, add_to_machine_state, remove_from_machine_state
from ssh_scheduler.machine_cost_model import machine_cost, get_best_gpu, get_process_gpu_limit, is_over_limit

class ExampleArgs:
    def __init__(self):
        self.no_gpu_required = False
        self.gpu_memory_required = 1000
        self.gpu_utilization = 0.3
        self.no_reserve_gpu = True
        self.num_cpus = 2
        self.memory_required = 2000
        self.reserve = False

example_machine_state = {"cpu_usage": 0.124, "mem_free": 30607, "cpu_count": 24, "gpus": [{"name": "GeForce RTX 2060", "mem": 5934, "free": 5933, "utilization": 0.0}, {"name": "GeForce RTX 2060", "mem": 5932, "free": 5931, "utilization": 0.0}]}

def test_invertible():
    machine_args = ExampleArgs()
    machine_state = copy.deepcopy(example_machine_state)
    init_machine_limit(machine_state)
    orig_machine_state = copy.deepcopy(machine_state)
    assert not is_over_limit(machine_cost(machine_args, machine_state))
    assert get_best_gpu(machine_args, machine_state) == 0
    assert len(get_process_gpu_limit(machine_state, machine_args)) == 6

    for j in range(4):
        for i in range(2):
            machine_state = add_to_machine_state(machine_state, machine_args, i)

    machine_state2 = copy.deepcopy(orig_machine_state)
    for i in range(2):
        for j in range(4):
            machine_state2 = add_to_machine_state(machine_state2, machine_args, i)

    assert machine_cost(machine_args, machine_state2) == machine_cost(machine_args, machine_state)
    assert machine_cost(machine_args, orig_machine_state) != machine_cost(machine_args, machine_state)
    assert machine_state2 == machine_state
    assert machine_state2 != orig_machine_state
    for i in range(2):
        for j in range(4):
            machine_state = remove_from_machine_state(machine_state, i)

    assert machine_state == orig_machine_state
