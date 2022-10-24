
def aggregate_sum(data_buffer, experiment):
    return data_buffer.reshape(int(experiment.N_cycles), int(experiment.N_clock_ticks_per_cycle)).sum(axis=0)

class Experiment:

    def run(self, N_cycles = 500000, post_process_function = None, *args, **kwargs):
        raise NotImplementedError()

    def experimental_conditions(self):
        raise NotImplementedError()
