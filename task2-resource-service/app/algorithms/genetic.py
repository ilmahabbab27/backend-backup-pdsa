"""Evolutionary allocation search for Task 2.

The genetic strategy keeps a population of candidate assignment chromosomes,
selects fitter individuals, recombines them, and repairs infeasible offspring to
respect station and vehicle constraints.
"""

from __future__ import annotations

from random import Random

from app.algorithms.common import Problem
from app.algorithms.greedy import greedy


def genetic(problem: Problem):
    """Seeded population, tournament selection, crossover, mutation, repair, elitism."""
    options = problem.options
    rng = Random(options.seed)
    size = len(problem.slots)
    if not size:
        return [], {"generations": 0, "fitness_history": []}

    # Start from a fast greedy solution and fill the rest of the population with
    # randomly repaired variants to create a diverse search space.
    population = [greedy(problem)]
    population += [problem.repair([None] * size, rng) for _ in range(options.population_size - 1)]
    history = []
    for _ in range(options.generations):
        ranked = sorted(population, key=problem.score)
        history.append(problem.score(ranked[0]))

        # Keep the best individuals as elite parents for the next generation.
        offspring = [ranked[0][:], ranked[1][:]]
        while len(offspring) < options.population_size:
            # Tournament selection favours lower-scoring chromosomes while still
            # retaining a bit of genetic diversity.
            parents = [min(rng.sample(population, 3), key=problem.score) for _ in range(2)]
            cut = rng.randrange(size + 1)
            child = parents[0][:cut] + parents[1][cut:]
            for slot in range(size):
                if rng.random() < options.mutation_rate:
                    child[slot] = rng.choice([None, *problem.candidates[slot]])
            offspring.append(problem.repair(child))
        population = offspring
    best = min(population, key=problem.score)
    history.append(problem.score(best))
    return best, {"generations": options.generations, "population_size": options.population_size,
                  "seed": options.seed, "fitness_history": history}


__all__ = ["genetic"]
