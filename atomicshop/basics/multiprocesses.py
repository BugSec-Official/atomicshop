import multiprocessing
import multiprocessing.managers
import os
import queue
import threading
import concurrent.futures
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import deque
from typing import Callable
import time

from ..import system_resources


def kill_processes(
        processes: list
):
    """Terminate all children with SIGTERM (or SIGKILL if you like)."""
    # Ask OS to terminate all processes in the list.
    for p in processes:
        if p.is_alive():
            p.terminate()
    time.sleep(1)  # give processes a chance to exit cleanly
    # Force kill all processes in the list.
    for p in processes:
        if p.is_alive():
            p.kill()
    for p in processes:          # wait for everything to disappear
        p.join()


def is_process_crashed(
        processes: list[multiprocessing.Process]
) -> tuple[int, str] | tuple[None, None]:
    """
    Check if any of the processes in the list is not alive.
    :param processes: list, list of multiprocessing.Process objects.
    :return: tuple(int, string) or None.
        tuple(0 if any finished cleanly, process name).
        tuple(1 (or exit code integer) if any process crashed, process_name).
        None if all processes are still alive.

    ==============================================

    Usage example:
    processes = [multiprocessing.Process(target=some_function) for _ in range(5)]

    for p in processes:
        p.start()

    # Check if any process has crashed
    try:
        while True:
            # Poll every second; you can use a shorter sleep if you prefer.
            result, process_name = is_process_crashed(processes)
            # If result is None, all processes are still alive.
            if result is not None:
                # If result is 0 or 1, we can exit the loop.
                print(f"Process [{process_name}] finished with exit code {result}.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("Ctrl-C caught – terminating children…")
        kill_all(processes)
        sys.exit(0)
    """

    for p in processes:
        if p.exitcode is not None:  # the process is *dead*
            kill_processes(processes)  # stop the rest
            if p.exitcode == 0:
                # print(f"{p.name} exited cleanly; shutting down.")
                return 0, p.name
            else:
                # print(f"{p.name} crashed (exitcode {p.exitcode}). Shutting everything down.")
                return p.exitcode, p.name

    return None, None  # all processes are still alive


def process_wrap_queue(function_reference: Callable, *args, **kwargs):
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
            process_function: Callable,
            input_list: list,
            max_workers: int = None,
            cpu_percent_max: int = 80,
            memory_percent_max: int = 80,
            wait_time: float = 5,
            system_monitor_manager_dict: multiprocessing.managers.DictProxy = None
    ):
        """
        MultiProcessor class. Used to execute functions in parallel. The result of each execution is fed back
            to the provided function. Making it sort of recursive execution.
        :param process_function: function, function to execute on the input list.
        :param input_list: list, list of inputs to process.
        :param max_workers: integer, number of workers to execute functions in parallel. Default is None, which
            is the number of CPUs that will be counted automatically by the multiprocessing module.
        :param cpu_percent_max: integer, maximum CPU percentage. Above that usage, we will wait before starting new
            execution.
        :param memory_percent_max: integer, maximum memory percentage. Above that usage, we will wait, before starting
            new execution.
        :param wait_time: float, time to wait if the CPU or memory usage is above the maximum percentage.
        :param system_monitor_manager_dict: multiprocessing.managers.DictProxy, shared manager dict for
            system monitoring. The object is the output of atomicshop.system_resource_monitor.
            If you are already running this monitor, you can pass the manager_dict to both the system monitor and this
            class to share the system resources data.
            If this is used, the system resources will be checked before starting each new execution from this
            shared dict instead of performing new checks.

        Usage Examples:
            def unpack_file(file_path):
                # Process the file at file_path and unpack it.
                # Return a list of new file paths that were extracted from the provided path.
                return [new_file_path1, new_file_path2]  # Example return value

            # List of file paths to process
            file_paths = ["path1", "path2", "path3"]

            # Note: unpack_file Callable is passed to init without parentheses.

            1. Providing the list directly to process at once:
                # Initialize the processor.
                processor = MultiProcessor(
                    process_function=unpack_file,
                    input_list=file_paths,
                    max_workers=4,  # Number of parallel workers
                    cpu_percent_max=80,  # Max CPU usage percentage
                    memory_percent_max=80,  # Max memory usage percentage
                    wait_time=5  # Time to wait if resources are overused
                )

                # Process the list of files at once.
                processor.run_process()
                # Shutdown the pool processes after processing.
                processor.shutdown_pool()

            2. Processing each file in the list differently then adding to the list of the multiprocessing instance then executing.
                # Initialize the processor once, before the loop, with empty input_list.
                processor = MultiProcessor(
                    process_function=unpack_file,
                    input_list=[],
                    max_workers=4,  # Number of parallel workers
                    cpu_percent_max=80,  # Max CPU usage percentage
                    memory_percent_max=80,  # Max memory usage percentage
                    wait_time=5  # Time to wait if resources are overused
                )

                for file_path in file_paths:
                    # <Process each file>.
                    # Add the result to the input_list of the processor.
                    processor.input_list.append(file_path)

                # Process the list of files at once.
                processor.run_process()
                # Shutdown the pool processes after processing.
                processor.shutdown_pool()

            3. Processing each file in the list separately, since we're using an unpacking function that
               will create more files, but the context for this operation is different for extraction
               of each main file inside the list:

                # Initialize the processor once, before the loop, with empty input_list.
                processor = MultiProcessor(
                    process_function=unpack_file,
                    input_list=[],
                    max_workers=4,  # Number of parallel workers
                    cpu_percent_max=80,  # Max CPU usage percentage
                    memory_percent_max=80,  # Max memory usage percentage
                    wait_time=5  # Time to wait if resources are overused
                )

                for file_path in file_paths:
                    # <Process each file>.
                    # Add the result to the input_list of the processor.
                    processor.input_list.append(file_path)
                    # Process the added file path separately.
                    processor.run_process()

                # Shutdown the pool processes after processing.
                processor.shutdown_pool()
        """

        self.process_function: Callable = process_function
        self.input_list: list = input_list
        self.max_workers: int = max_workers
        self.cpu_percent_max: int = cpu_percent_max
        self.memory_percent_max: int = memory_percent_max
        self.wait_time: float = wait_time
        self.system_monitor_manager_dict: multiprocessing.managers.DictProxy = system_monitor_manager_dict

        # Create the pool once and reuse it
        self.pool: multiprocessing.Pool = multiprocessing.Pool(processes=self.max_workers)

        # Keep track of outstanding async results across calls
        self.async_results: list = []

    def run_process(self):
        """
        Start with the items currently in self.input_list, but whenever a task
        finishes schedule the children it returns *right away*.
        The loop ends when there are no more outstanding tasks.
        """
        # ----------  internal helpers  ----------
        outstanding = 0  # tasks that have been submitted but not yet finished
        done_event = threading.Event()  # let the main thread wait until work is over

        def _submit(item):
            nonlocal outstanding
            # Wait for resources *before* submitting a new job
            system_resources.wait_for_resource_availability(
                cpu_percent_max=self.cpu_percent_max,
                memory_percent_max=self.memory_percent_max,
                wait_time=self.wait_time,
                system_monitor_manager_dict=self.system_monitor_manager_dict
            )
            outstanding += 1
            self.pool.apply_async(
                self.process_function,
                (item,),
                callback=_on_finish,  # called in the main process when result is ready
                error_callback=_on_error
            )

        def _on_finish(result):
            """Pool calls this in the parent process thread when a job completes."""
            nonlocal outstanding
            outstanding -= 1

            # The worker returned a list of new items – submit them immediately
            if result:
                for child in result:
                    _submit(child)

            # If no work left, release the waiter
            if outstanding == 0:
                done_event.set()

        def _on_error(exc):
            """Propagate the first exception and stop everything cleanly."""
            done_event.set()
            raise exc  # let your code deal with it – you can customise this

        # ----------  kick‑off  ----------
        # Schedule the items we already have
        for item in self.input_list:
            _submit(item)

        # Clear the input list; after this point everything is driven by callbacks
        self.input_list.clear()

        # Wait until all recursively spawned work is finished
        done_event.wait()

    def shutdown(self):
        """Shuts down the pool gracefully."""
        if self.pool:
            self.pool.close()  # Stop accepting new tasks
            self.pool.join()  # Wait for all tasks to complete
            self.pool = None


class _MultiProcessorRecursiveWithProcessPoolExecutor:
    def __init__(
            self,
            process_function: Callable,
            input_list: list,
            max_workers: int = None,
            cpu_percent_max: int = 80,
            memory_percent_max: int = 80,
            wait_time: float = 5,
            system_monitor_manager_dict: multiprocessing.managers.DictProxy = None
    ):
        """
        THIS CLASS USES THE concurrent.futures.ProcessPoolExecutor to achieve parallelism.
        For some reason I got freezes on exceptions without the exception output after the run_process() method finished
        and the pool remained open. So, using the MultiProcessorRecursive instead.

        MultiProcessor class. Used to execute functions in parallel. The result of each execution is fed back
            to the provided function. Making it sort of recursive execution.
        :param process_function: function, function to execute on the input list.
        :param input_list: list, list of inputs to process.
        :param max_workers: integer, number of workers to execute functions in parallel. Default is None, which
            is the number of CPUs that will be counted automatically by the multiprocessing module.
        :param cpu_percent_max: integer, maximum CPU percentage. Above that usage, we will wait before starting new
            execution.
        :param memory_percent_max: integer, maximum memory percentage. Above that usage, we will wait, before starting
            new execution.
        :param wait_time: float, time to wait if the CPU or memory usage is above the maximum percentage.
        :param system_monitor_manager_dict: multiprocessing.managers.DictProxy, shared manager dict for
            system monitoring. The object is the output of atomicshop.system_resource_monitor.
            If you are already running this monitor, you can pass the manager_dict to both the system monitor and this
            class to share the system resources data.
            If this is used, the system resources will be checked before starting each new execution from this
            shared dict instead of performing new checks.

        Usage Examples:
            def unpack_file(file_path):
                # Process the file at file_path and unpack it.
                # Return a list of new file paths that were extracted from the provided path.
                return [new_file_path1, new_file_path2]  # Example return value

            # List of file paths to process
            file_paths = ["path1", "path2", "path3"]

            # Note: unpack_file Callable is passed to init without parentheses.

            1. Providing the list directly to process at once:
                # Initialize the processor.
                processor = MultiProcessor(
                    process_function=unpack_file,
                    input_list=file_paths,
                    max_workers=4,  # Number of parallel workers
                    cpu_percent_max=80,  # Max CPU usage percentage
                    memory_percent_max=80,  # Max memory usage percentage
                    wait_time=5  # Time to wait if resources are overused
                )

                # Process the list of files at once.
                processor.run_process()
                # Shutdown the pool processes after processing.
                processor.shutdown_pool()

            2. Processing each file in the list differently then adding to the list of the multiprocessing instance then executing.
                # Initialize the processor once, before the loop, with empty input_list.
                processor = MultiProcessor(
                    process_function=unpack_file,
                    input_list=[],
                    max_workers=4,  # Number of parallel workers
                    cpu_percent_max=80,  # Max CPU usage percentage
                    memory_percent_max=80,  # Max memory usage percentage
                    wait_time=5  # Time to wait if resources are overused
                )

                for file_path in file_paths:
                    # <Process each file>.
                    # Add the result to the input_list of the processor.
                    processor.input_list.append(file_path)

                # Process the list of files at once.
                processor.run_process()
                # Shutdown the pool processes after processing.
                processor.shutdown_pool()

            3. Processing each file in the list separately, since we're using an unpacking function that
               will create more files, but the context for this operation is different for extraction
               of each main file inside the list:

                # Initialize the processor once, before the loop, with empty input_list.
                processor = MultiProcessor(
                    process_function=unpack_file,
                    input_list=[],
                    max_workers=4,  # Number of parallel workers
                    cpu_percent_max=80,  # Max CPU usage percentage
                    memory_percent_max=80,  # Max memory usage percentage
                    wait_time=5  # Time to wait if resources are overused
                )

                for file_path in file_paths:
                    # <Process each file>.
                    # Add the result to the input_list of the processor.
                    processor.input_list.append(file_path)
                    # Process the added file path separately.
                    processor.run_process()

                # Shutdown the pool processes after processing.
                processor.shutdown_pool()
        """

        self.process_function: Callable = process_function
        self.input_list: list = input_list
        self.cpu_percent_max: int = cpu_percent_max
        self.memory_percent_max: int = memory_percent_max
        self.wait_time: float = wait_time
        self.system_monitor_manager_dict: multiprocessing.managers.DictProxy = system_monitor_manager_dict

        if max_workers is None:
            max_workers = os.cpu_count()
        self.max_workers: int = max_workers

        # Create the executor once and reuse it.
        # noinspection PyTypeChecker
        self.executor: ProcessPoolExecutor = None

    def _ensure_executor(self):
        """Create a new pool if we do not have one or if the old one was shut."""
        if self.executor is None or getattr(self.executor, '_shutdown', False):
            self.executor = ProcessPoolExecutor(max_workers=self.max_workers)

    def run_process(self):
        # Make sure we have a live executor
        self._ensure_executor()

        work_q = deque(self.input_list)  # breadth‑first queue
        self.input_list.clear()
        futures = set()

        # helper to submit jobs up to the concurrency limit
        def _fill():
            while work_q and len(futures) < self.max_workers:
                item = work_q.popleft()
                system_resources.wait_for_resource_availability(
                    cpu_percent_max=self.cpu_percent_max,
                    memory_percent_max=self.memory_percent_max,
                    wait_time=self.wait_time,
                    system_monitor_manager_dict=self.system_monitor_manager_dict
                )
                futures.add(self.executor.submit(self.process_function, item))

        _fill()  # start the first wave

        while futures:
            for fut in as_completed(futures):
                futures.remove(fut)  # a slot just freed up

                # propagate worker exceptions immediately
                children = fut.result()

                # schedule the newly discovered items
                if children:
                    work_q.extend(children)

                _fill()  # keep the pool saturated
                break  # leave the for‑loop so as_completed resets

    def shutdown(self):
        """Shuts down the executor gracefully."""
        if self.executor:
            self.executor.shutdown(wait=True)  # blocks until all tasks complete
            self.executor = None


class ConcurrentProcessorRecursive:
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
        Exactly the same as MultiProcessorRecursive, but uses the ProcessPoolExecutor of concurrent.futures module
        instead of multiprocessing.Pool.
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
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.process_function, item): item for item in self.input_list}
            self.input_list = []

            while futures:
                # Wait for the next future to complete
                done, _ = concurrent.futures.wait(futures.keys(), return_when=concurrent.futures.FIRST_COMPLETED)

                for future in done:
                    item = futures.pop(future)
                    try:
                        result = future.result()
                        # Extend new_input_list with the result
                        self.input_list.extend(result)
                    except Exception as e:
                        print(f"An error occurred while processing {item}: {e}")

                    while self.input_list:
                        # Check system resources and start new tasks if resources are available
                        system_resources.wait_for_resource_availability(
                            cpu_percent_max=self.cpu_percent_max,
                            memory_percent_max=self.memory_percent_max,
                            wait_time=self.wait_time)

                        new_item = self.input_list.pop(0)
                        new_future = executor.submit(self.process_function, new_item)
                        futures[new_future] = new_item


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


class _ConcurrentProcessorTest:
    def __init__(self, max_workers: int = 2, initialize_at_start: bool = False):
        """
        ConcurrentProcessorTest class. Used to execute functions in parallel with the ProcessPoolExecutor.

        :param max_workers: integer, number of workers to execute functions in parallel.
        :param initialize_at_start: boolean, if True, the workers will be initialized at the start of the class.

        Usage 1:
            if __name__ == "__main__":
            concurator = ConcurrentProcessorTest(max_workers=4, initialize_at_start=True)

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
