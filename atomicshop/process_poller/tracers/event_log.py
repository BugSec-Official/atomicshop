from pathlib import Path

from ...wrappers.pywin32w.win_event_log.subscribes import process_create, process_terminate
from .. import tracer_base


class TracerEventlog(tracer_base.Tracer):
    """
    Tracer subclass for getting the list of processes with Windows Event Log Subscription.
    """
    def __init__(
            self,
            process_queue
    ):
        """
        :param process_queue: Queue. The queue to put the processes in. If None, the processes will not be put in the
            queue.
        """
        super().__init__()

        self.tracer_instance = process_create.ProcessCreateSubscriber()

        self.process_queue = process_queue

        # This function is used in the thread start in the main Tracer class, 'start' function.
        self._cycle_callable = self.emit_cycle

    def start(self):
        """
        Start the tracer.
        """
        super().start()

    def emit_cycle(self):
        """
        Get the list of processes.
        """

        # Get the current processes and reinitialize the instance of the dict.
        current_cycle: dict = self.tracer_instance.emit()
        current_processes: dict = {int(current_cycle['NewProcessIdInt']): {
            'name': Path(current_cycle['NewProcessName']).name,
            'cmdline': current_cycle['CommandLine']}
        }

        return current_processes
