from .. import tracer_base
from ...etws.traces import trace_sysmon_process_creation


class TracerSysmonEtw(tracer_base.Tracer):
    """
    Tracer subclass for getting the list of processes with SysMon ETW.
    """
    def __init__(
            self,
            attrs: list = None,
            settings: dict = None,
            process_queue=None
    ):
        """
        :param attrs: list. Default is ['pid', 'original_file_name', 'command_line'].
            The list of attributes to get from the sysmon trace output. Check SysmonProcessCreationTrace class for
            available attributes.
        :settings: dict. The settings dictionary:
            'sysmon_etw_session_name': str. The Sysmon ETW session name. If None, the default from
                'trace_sysmon_process_creation' will be used.
            'sysmon_directory': str. The directory where Sysmon.exe resides. If None, the default from
                'trace_sysmon_process_creation' will be used.
        :param process_queue: Queue. The queue to put the processes in. If None, the processes will not be put in the
            queue.
        """
        super().__init__()

        if not attrs:
            attrs = ['ProcessId', 'OriginalFileName', 'CommandLine']

        if not settings:
            settings = {
                'sysmon_etw_session_name': None,
                'sysmon_directory': None
            }

        self.tracer_instance = trace_sysmon_process_creation.SysmonProcessCreationTrace(
            attrs=attrs,
            session_name=settings.get('sysmon_etw_session_name'),
            close_existing_session_name=True,
            sysmon_directory=settings.get('sysmon_directory')
        )

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
        current_processes: dict = {int(current_cycle['ProcessId']): {
            'name': current_cycle['OriginalFileName'],
            'cmdline': current_cycle['CommandLine']}
        }

        return current_processes
