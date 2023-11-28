import multiprocessing
import queue
from concurrent.futures import ProcessPoolExecutor, as_completed

from ..import system_resources


def process_wrap_queue(function_reference, *args, **kwargs):
    """
    The function receives function reference and arguments, and executes the function in a thread.
    "_queue" means that a queue.put() is used to store the result of the function and queue.get() to output it.

    :param function_reference: function reference to execute.
    :param args: arguments for the function.
    :param kwargs: keyword arguments for the function.
    :return: output of the referenced function.
    """

    def threaded_function():
        queue_object.put(function_reference(*args, **kwargs))

    # Create queue object.
    queue_object = queue.Queue()

    # Create thread object.
    process_object = multiprocessing.Process(target=threaded_function)

    # Start thread.
    process_object.start()
    # Wait for thread to finish.
    process_object.join()

    return queue_object.get()


class MultiProcessorRecursive:
    def __init__(
            self,
            process_function,
            input_list: list,
            max_workers: int = None,
            cpu_percent_max: int = 80,
            memory_percent_max: int = 80,
            wait_time: float = 5
    ):
        """
        MultiProcessor class. Used to execute functions in parallel. The result of each execution is feeded back
            to the provided function. Making it sort of recursive execution.
        :param process_function: function, function to execute on the input list.
        :param input_list: list, list of inputs to process.
        :param max_workers: integer, number of workers to execute functions in parallel. Default is None, which
            is the number of CPUs.
        :param cpu_percent_max: integer, maximum CPU percentage. Above that usage, we will wait before starting new
            execution.
        :param memory_percent_max: integer, maximum memory percentage. Above that usage, we will wait, before starting
            new execution.
        :param wait_time: float, time to wait if the CPU or memory usage is above the maximum percentage.

        Usage:
            def unpack_file(file_path):
                # Process the file at file_path and unpack it.
                # Return a list of new file paths that were extracted from the provided path.
                return [new_file_path1, new_file_path2]  # Example return value

            # List of file paths to process
            file_paths = ["path1", "path2", "path3"]

            # Create an instance of MultiProcessor
            # Note: unpacking.unpack_file is passed without parentheses
            processor = MultiProcessor(
                process_function=unpack_file,
                input_list=file_paths,
                max_workers=4,  # Number of parallel workers
                cpu_percent_max=80,  # Max CPU usage percentage
                memory_percent_max=80,  # Max memory usage percentage
                wait_time=5  # Time to wait if resources are overused
            )

            # Run the processing
            processor.run_process()
        """

        self.process_function = process_function
        self.input_list: list = input_list
        self.max_workers: int = max_workers
        self.cpu_percent_max: int = cpu_percent_max
        self.memory_percent_max: int = memory_percent_max
        self.wait_time: float = wait_time

    def run_process(self):
        with multiprocessing.Pool(processes=self.max_workers) as pool:
            while self.input_list:
                system_resources.wait_for_resource_availability(
                    cpu_percent_max=self.cpu_percent_max,
                    memory_percent_max=self.memory_percent_max,
                    wait_time=self.wait_time)

                # Apply the provided function to the items in the input list
                results = pool.map(self.process_function, self.input_list)

                # Flatten list of lists and update the queue
                self.input_list = [item for sublist in results for item in sublist]


class _MultiProcessorTest:
    def __init__(self, worker_count: int = 8, initialize_at_start: bool = True):
        """
        MultiProcessor class. Used to execute functions in parallel.
        :param worker_count: integer, number of workers to execute functions in parallel.
        :param initialize_at_start: boolean, if True, the workers will be initialized at the start of the class.

        Usage:
            # Example functions
            def my_function1(x):
                return x * x

            def my_callback(result):
                print(f"Result received: {result}")

            # Usage example
            if __name__ == "__main__":
                processor = MultiProcessor()

                # Adding tasks with callback (asynchronous)
                for i in range(5):
                    processor.add_task(my_function1, i, callback=my_callback)

                # Adding a task and waiting for the result (synchronous)
                result = processor.add_task(my_function1, 10, wait=True)
                print(f"Synchronous result: {result}")

                # Shutdown and wait for all tasks to complete
                processor.shutdown()
        """

        self.worker_count: int = worker_count
        self.task_queue = multiprocessing.Queue()
        self.result_queue = multiprocessing.Queue()
        self.workers: list = list()

        if initialize_at_start:
            self._init_workers()

    def _worker(self):
        while True:
            task = self.task_queue.get()
            if task is None:  # Termination signal
                break
            func, args, kwargs, callback, return_result = task
            try:
                result = func(*args, **kwargs)
                if callback:
                    callback(result)
                if return_result:
                    self.result_queue.put(result)
            except Exception as e:
                if callback:
                    callback(e)
                if return_result:
                    self.result_queue.put(e)

    def _init_workers(self):
        for _ in range(self.worker_count):
            p = multiprocessing.Process(target=self._worker)
            p.start()
            self.workers.append(p)

    def add_task(self, func, *args, callback=None, wait=False, **kwargs):
        """
        Add a task to the queue.
        :param func: reference, function to execute.
        :param args: arguments for the function.
        :param callback: reference, function to execute after the task is completed. The result of the task will be
            passed to the callback function.
        :param wait: boolean, if True, the function will wait for the task to complete and return the result.
        :param kwargs: keyword arguments for the function.
        :return:
        """
        if wait:
            self.task_queue.put((func, args, kwargs, None, True))
            return self.result_queue.get()
        else:
            self.task_queue.put((func, args, kwargs, callback, False))
            return None

    def shutdown(self):
        # Signal workers to exit
        for _ in self.workers:
            self.task_queue.put(None)

        # Wait for all workers to finish
        for p in self.workers:
            p.join()


class _MultiConcuratorTest:
    def __init__(self, max_workers: int = 2, initialize_at_start: bool = False):
        """
        MultiConcurator class. Used to execute functions in parallel with the ProcessPoolExecutor.

        :param max_workers: integer, number of workers to execute functions in parallel.
        :param initialize_at_start: boolean, if True, the workers will be initialized at the start of the class.

        Usage 1:
            if __name__ == "__main__":
            concurator = MultiConcurator(max_workers=4, initialize_at_start=True)

            # ... add tasks to concurator ...

            concurator.wait_for_completion()

            # Continuously get and process results
            for result in concurator.get_results():
                print(result)

            concurator.shutdown()

        Usage 2:
            # Basic Usage - Executing Functions in Parallel
            This example shows how to execute a simple function in parallel.

            def square(number):
                return number * number

            if __name__ == "__main__":
                concurator = MultiConcurator(max_workers=4, initialize_at_start=True)

                # Submit tasks
                for num in range(10):
                    concurator.add_to_queue(square, num)

                # Wait for completion and handle results
                concurator.wait_for_completion()

                # Retrieve results
                while not concurator.queue.empty():
                    result = concurator.queue.get()
                    print(result)

                concurator.shutdown()

        Usage 3:
            # Handling Results with a Callback Function
            # This example demonstrates handling the results of each task using a callback function.

            def multiply(x, y):
                return x * y

            def handle_result(result):
                print(f"Result: {result}")

            if __name__ == "__main__":
                concurator = MultiConcurator(max_workers=4, initialize_at_start=True)

                for i in range(5):
                    concurator.add_to_queue(multiply, i, i+1)

                concurator.wait_for_completion(handle_result)
                concurator.shutdown()

        Usage 4:
            # Dynamically Initializing the Executor
            # This example shows how to initialize the executor dynamically and process tasks.

            def compute_power(base, exponent):
                return base ** exponent

            if __name__ == "__main__":
                concurator = MultiConcurator(max_workers=3)

                # Initialize executor when needed
                concurator.init_executor()

                for i in range(1, 5):
                    concurator.add_to_queue(compute_power, i, 2)

                concurator.wait_for_completion()
                while not concurator.queue.empty():
                    print(concurator.queue.get())

                concurator.shutdown()

        Usage 5:
            # Handling Exceptions in Tasks
            # This example demonstrates how you can handle exceptions that might occur in the tasks.

            def risky_division(x, y):
                if y == 0:
                    raise ValueError("Cannot divide by zero")
                return x / y

            def handle_result(result):
                if isinstance(result, Exception):
                    print(f"Error occurred: {result}")
                else:
                    print(f"Result: {result}")

            if __name__ == "__main__":
                concurator = MultiConcurator(max_workers=4, initialize_at_start=True)

                concurator.add_to_queue(risky_division, 10, 2)
                concurator.add_to_queue(risky_division, 10, 0)  # This will raise an exception

                concurator.wait_for_completion(handle_result)
                concurator.shutdown()
        """

        self.executor = None
        self.max_workers: int = max_workers
        self.futures: list = list()
        self.queue = multiprocessing.Queue()

        if initialize_at_start:
            self.init_executor()

    def init_executor(self):
        if self.executor is None:
            self.executor = ProcessPoolExecutor(max_workers=self.max_workers)

    def add_to_queue(self, func, *args, **kwargs):
        if self.executor is None:
            raise RuntimeError("Executor has not been initialized. Call init_executor() first.")
        future = self.executor.submit(func, *args, **kwargs)
        self.futures.append(future)
        return future

    def wait_for_completion(self, handle_result=None):
        for future in as_completed(self.futures):
            result = future.result()
            if handle_result:
                handle_result(result)
            else:
                self.queue.put(result)

    def get_results(self):
        while not self.queue.empty():
            yield self.queue.get()

    def shutdown(self):
        if self.executor is not None:
            self.executor.shutdown()
            self.executor = None
