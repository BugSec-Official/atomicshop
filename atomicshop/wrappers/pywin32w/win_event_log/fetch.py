import win32evtlog
import win32security
import win32con


def get_latest_events(
    server_ip: str = ".",
    username: str = None,
    password: str = None,
    domain: str = ".",
    log_name: str = "Security",
    count: int = None,
    event_id_list: list[int] | None = None
):
    """
    Fetch latest `count` events from a Windows Event Log (local or remote) using pywin32.

    - If username/password are None => use current security context.
    - If server_ip is ".", "localhost", "127.0.0.1", "" or None => open local log.
    - If count is None => return *all* events in the log.
    - If event_id_list is not None => only return events whose EventID is in that list.

    :param server_ip: IPv4/hostname of remote machine, or "." / None for local
    :param username: Username to authenticate with (optional)
    :param password: Password for the user (optional)
    :param domain: Domain or computer name; ignored if username is None.
                   If None and username is given, "." is used.
    :param log_name: Log name (e.g. "Security", "System", "Application")
    :param count: Number of most recent events to return, or None for all
    :param event_id_list: List of Event IDs (low 16-bit) to include, or None for all
    :return: List of dicts describing events (most recent first)
    """

    # Normalize server for OpenEventLog: None means "local machine"
    normalized_server = server_ip
    if server_ip in (None, "", ".", "localhost", "127.0.0.1"):
        normalized_server = None

    # Max events logic: None => infinite
    max_events = float("inf") if count is None else count

    # Precompute set of event IDs for fast membership checks
    event_ids_set = set(event_id_list) if event_id_list is not None else None

    # Decide whether we need impersonation
    use_impersonation = username is not None and password is not None

    h_user = None
    events = []

    try:
        if use_impersonation:
            if domain is None:
                domain = "."

            # Log on with explicit credentials and impersonate for the remote call
            # LOGON32_LOGON_NEW_CREDENTIALS lets us use these creds for remote access
            # while keeping the local token mostly unchanged.
            h_user = win32security.LogonUser(
                username,
                domain,
                password,
                win32con.LOGON32_LOGON_NEW_CREDENTIALS,
                win32con.LOGON32_PROVIDER_WINNT50,
            )

            win32security.ImpersonateLoggedOnUser(h_user)

        # Connect to remote event log
        # `server_ip` can be an IP or hostname; no need for leading "\\".
        # local if normalized_server is None.
        h_log = win32evtlog.OpenEventLog(normalized_server, log_name)

        flags = (
            win32evtlog.EVENTLOG_BACKWARDS_READ
            | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        )

        offset = 0  # not used with BACKWARDS_READ + SEQUENTIAL_READ, but kept for clarity

        while len(events) < max_events:
            records = win32evtlog.ReadEventLog(h_log, flags, offset)
            if not records:
                break

            for ev in records:
                # Low 16 bits are the actual Event ID
                eid = ev.EventID & 0xFFFF

                # If filtering by event IDs, skip others
                if event_ids_set is not None and eid not in event_ids_set:
                    continue

                raw_strings = list(ev.StringInserts or [])
                strings_dict = _parse_strings(eid, ev.SourceName, raw_strings)

                evt = {
                    "RecordNumber": ev.RecordNumber,
                    "TimeGenerated": ev.TimeGenerated.Format(),  # string time
                    "ComputerName": ev.ComputerName,
                    "SourceName": ev.SourceName,
                    # Low 16 bits are the actual Event ID
                    "EventID": ev.EventID & 0xFFFF,
                    "EventType": ev.EventType,
                    "EventCategory": ev.EventCategory,
                    "Strings": raw_strings,
                    "StringsDict": strings_dict,
                }
                events.append(evt)

                if len(events) >= max_events:
                    break

        win32evtlog.CloseEventLog(h_log)

    finally:
        # Clean up impersonation if we used it, Always revert impersonation and close handle
        if use_impersonation and h_user is not None:
            win32security.RevertToSelf()
            h_user.Close()

    # `events` is in newest to oldest already because of BACKWARDS_READ.
    return events


def _parse_strings(event_id: int, source_name: str, strings: list[str]) -> dict:
    """
    Convert the raw 'Strings' list into a dictionary with friendly field names
    for specific event IDs. For unknown events, fall back to String1, String2, ...

    Currently has a special mapping for:
      - 5156 (Security log, WFP allowed connection)
    """
    if not strings:
        return {}

    # Normalize source name a bit
    src = (source_name or "").lower()

    # Special-case: Security 5156 (Windows Filtering Platform has permitted a connection)
    # Insertion strings (in order) are:
    #   1 Process ID
    #   2 Application Name
    #   3 Direction
    #   4 Source Address
    #   5 Source Port
    #   6 Destination Address
    #   7 Destination Port
    #   8 Protocol
    #   9 Filter Run-Time ID
    #   10 Layer Name
    #   11 Layer Run-Time ID
    if event_id == 5156 and "security-auditing" in src:
        keys_5156 = [
            "Process ID",
            "Application Name",
            "Direction",
            "Source Address",
            "Source Port",
            "Destination Address",
            "Destination Port",
            "Protocol",
            "Filter Run-Time ID",
            "Layer Name",
            "Layer Run-Time ID",
        ]
        return {
            key: strings[i]
            for i, key in enumerate(keys_5156)
            if i < len(strings)
        }

    # Default: generic mapping
    return {f"String{i+1}": s for i, s in enumerate(strings)}