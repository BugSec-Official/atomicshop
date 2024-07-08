import os
import datetime

import win32com.client
import pythoncom


TRIGGER_ONE_TIME: int = 1
TRIGGER_DAILY: int = 2
TRIGGER_AT_SYSTEM_STARTUP: int = 8
TRIGGER_ON_LOGON: int = 9


def create_on_logon_task_with_system_privileges(exe_file_path: str, task_name: str, user_id: str = None):
    """
    This function will add a task to the Windows Task Scheduler with system privileges.

    :param exe_file_path: The path to your executable file.
    :param task_name: The name of the task to create in the Task Scheduler.
    :param user_id: The user ID to run the task as.
        None: the task will run for every user that logs on.
        "SYSTEM": is a common user ID to run tasks with system privileges.
    :return: True if the task was added successfully, False otherwise.
    """

    scheduler = win32com.client.Dispatch('Schedule.Service')
    scheduler.Connect()

    root_folder = scheduler.GetFolder('\\')
    task_def = scheduler.NewTask(0)

    # Set up registration information for the task
    reg_info = task_def.RegistrationInfo
    reg_info.Description = f'Task to run {os.path.basename(exe_file_path)} at logon'
    reg_info.Author = 'Your Name'

    # Set up the principal for the task
    principal = task_def.Principal
    if user_id is not None:
        principal.UserId = user_id
    # principal.LogonType = 3  # TaskLogonTypeInteractiveToken, Only run when the user is logged on.
    principal.LogonType = 1  # 1 is for password not required
    principal.RunLevel = 1  # TaskRunLevelHighest

    # Create the logon trigger
    trigger = task_def.Triggers.Create(TRIGGER_ON_LOGON)
    if user_id:
        trigger.UserId = user_id
    trigger.Id = "LogonTriggerId"
    trigger.Enabled = True
    trigger.StartBoundary = datetime.datetime.now().isoformat()  # Set start boundary to current time in ISO format

    # Create the action to run the executable
    action = task_def.Actions.Create(0)  # 0 stands for TASK_ACTION_EXEC
    action.Path = exe_file_path
    action.WorkingDirectory = os.path.dirname(exe_file_path)
    action.Arguments = ''

    # Set task settings
    settings = task_def.Settings
    settings.Enabled = True
    settings.StartWhenAvailable = True
    settings.Hidden = False
    settings.StopIfGoingOnBatteries = False
    settings.DisallowStartIfOnBatteries = False
    # Sets the limit to zero, which means the task will run indefinitely. The default is 3 days.
    settings.ExecutionTimeLimit = 'PT0S'

    # Register the task
    root_folder.RegisterTaskDefinition(
        task_name, task_def, 6,  # 6 is for CREATE_OR_UPDATE
        None,  # No user (runs in system context)
        None,  # No password
        3
    )


def is_task_in_scheduler(task_name: str, scheduler_instance=None) -> bool:
    """
    This function will check if the task is in the Windows Task Scheduler.

    :param task_name: The name of the task to check in the Task Scheduler.
    :param scheduler_instance: The instance of the Task Scheduler to use.
        If None, a new instance will be created.
    :return: True if the task is in the Task Scheduler, False otherwise.
    """

    if scheduler_instance is None:
        scheduler_instance = win32com.client.Dispatch('Schedule.Service')
        scheduler_instance.Connect()

    try:
        root_folder = scheduler_instance.GetFolder('\\')
        root_folder.GetTask(task_name)
        return True
    except pythoncom.com_error as e:
        if e.hresult == -2147352567 and e.excepinfo[5] == -2147024894:  # HRESULT code for "Task does not exist"
            return False
        else:
            raise


def remove_task_from_scheduler(task_name: str) -> bool:
    """
    This function will remove the task from the Windows Task Scheduler.

    :param task_name: The name of the task to remove from the Task Scheduler.
    :return: True if the task was removed successfully, False otherwise.
    """

    scheduler_instance = win32com.client.Dispatch('Schedule.Service')
    scheduler_instance.Connect()

    if not is_task_in_scheduler(task_name, scheduler_instance=scheduler_instance):
        return False
    else:
        root_folder = scheduler_instance.GetFolder('\\')
        root_folder.GetTask(task_name)
        return True
