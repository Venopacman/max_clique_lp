'''
Max clique search BnB algorithm with cplex solver
'''
import sys

import cplex

from helper import *

GLOBAL_MAX_CLIQUE_SIZE = 0


def get_colored_sets(graph):
    strategies = [nx.algorithms.coloring.strategy_largest_first,
                  nx.algorithms.coloring.strategy_random_sequential,
                  nx.algorithms.coloring.strategy_independent_set,
                  nx.algorithms.coloring.strategy_connected_sequential_bfs,
                  nx.algorithms.coloring.strategy_connected_sequential_dfs,
                  nx.algorithms.coloring.strategy_saturation_largest_first]
    colored_sets = []

    for strategy in strategies:
        coloring_result = nx.algorithms.coloring.greedy_color(
            graph, strategy=strategy)
        for color in set(color for _, color in coloring_result.items()):
            colored_sets.append(
                [node for node, c in coloring_result.items() if c == color])
    return colored_sets


def construct_cplex_problem(graph):

    c = cplex.Cplex()
    c.set_log_stream('log.txt')
    c.set_error_stream('log.txt')
    c.set_warning_stream('log.txt')
    c.set_results_stream('log.txt')
    # We want to find a maximum of our objective function
    c.objective.set_sense(c.objective.sense.maximize)

    # The names of our variables
    names = ['x_{0}'.format(x) for x in graph.nodes]
    nodes_amount = len(names)
    objective = [1.0] * nodes_amount
    upper_bounds = objective.copy()

    c.variables.add(obj=objective,
                    ub=upper_bounds,
                    names=names,
                    types='C' * nodes_amount)

    # Constraints
    # Firsly, add constraints related to coloring sets
    coloring_sets = get_colored_sets(graph)
    color_set_size = len(coloring_sets)
    name_iter = iter(range(color_set_size + nodes_amount**2))
    color_rhs = [1.0] * color_set_size
    color_constraint_names = ['c_{0}'.format(
        next(name_iter)) for it in range(color_set_size)]
    color_constraint_senses = ['L'] * color_set_size
    color_constraints = []
    for color_set in coloring_sets:
        color_constraints.append([['x_{0}'.format(it)
                                   for it in color_set], [1.0] * len(color_set)])
    c.linear_constraints.add(lin_expr=color_constraints,
                             senses=color_constraint_senses,
                             rhs=color_rhs,
                             names=color_constraint_names)
    # Secondly, add constraints related to not connected edges
    not_connected_edges = nx.complement(graph).edges
    nce_set_size = len(not_connected_edges)
    nce_rhs = [1.0] * nce_set_size
    nce_constraint_names = ['c_{0}'.format(
        next(name_iter)) for it in range(nce_set_size)]
    nce_constraint_senses = ['L'] * nce_set_size
    nce_constraints = []
    for v1, v2 in not_connected_edges:
        nce_constraints.append(
            [['x_{0}'.format(v1), 'x_{0}'.format(v2)], [1.0] * 2])
    c.linear_constraints.add(lin_expr=nce_constraints,
                             senses=nce_constraint_senses,
                             rhs=nce_rhs,
                             names=nce_constraint_names)

    return c


def add_constraint(problem, bv, rhs):
    if rhs == 1.0:
        rhs = -1.0
        problem.linear_constraints.add(lin_expr=[[[bv], [-1.0]]],
                                       senses=['L'],
                                       rhs=[rhs],
                                       names=['branch_{0}_{1}'.format(bv, rhs)])
    else:
        problem.linear_constraints.add(lin_expr=[[[bv], [1.0]]],
                                       senses=['L'],
                                       rhs=[rhs],
                                       names=['branch_{0}_{1}'.format(bv, rhs)])
    return problem


def get_branching_variable(solution):
    return next((index for index, value in enumerate(solution) if not value.is_integer()), None)


def get_integer_solved_problem(problem):
    global GLOBAL_MAX_CLIQUE_SIZE
    try:
        problem.solve()
        solution = problem.solution.get_values()
    except cplex.exceptions.CplexSolverError:
        return 0
    if sum(solution) > GLOBAL_MAX_CLIQUE_SIZE:
        b_var = get_branching_variable(solution)
        if b_var is None:
            GLOBAL_MAX_CLIQUE_SIZE = int(sum(solution))
            return GLOBAL_MAX_CLIQUE_SIZE, solution
        return max(get_integer_solved_problem(add_constraint(cplex.Cplex(problem), b_var, 1.0)),
                   get_integer_solved_problem(add_constraint(
                       cplex.Cplex(problem), b_var, 0.0)),
                   key=lambda x: x[0] if isinstance(x, (list, tuple)) else x)
    return 0


@time_it
def get_max_clique(cplex_problem):
    return get_integer_solved_problem(cplex_problem)


def main():
    args = read_args()
    graph = parse_graph(args.path)
    try:
        with time_limit(args.time):
            qsize, solution = get_max_clique(construct_cplex_problem(graph))
            print('Maximum clique size: {0}'.format(qsize))
            print('Nodes: {0}'.format(list(i + 1 for i,
                                           value in enumerate(solution) if value == 1.0)))
    except TimeoutException:
        print("Timed out!")
        sys.exit(0)


if __name__ == '__main__':
    main()
