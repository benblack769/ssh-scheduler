import random
import numpy as np

def crossover(parent1, parent2):
    split_point = random.randrange(0,len(parent1))
    child1 = np.concatenate([parent1[:split_point], parent2[split_point]],axis=0)

def run_ga(fitness_fn,
                indiv_size,
                 population_size=50,
                 generations=100,
                 crossover_probability=0.8,
                 mutation_probability=0.2):
    n_crossovers = int(crossover_probability * population_size)
    n_mutations = int(mutation_probability * population_size)


    population = [np.random.randint(0,1+1,size=(indiv_size)) for i in range(population_size)]
    for gen in generations:
        new_pop = list(population)

        for i in range(n_crossovers):
            child1, child2 =
