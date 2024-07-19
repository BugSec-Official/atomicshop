ETW_DNS = {
    'provider_name': 'Microsoft-Windows-DNS-Client',
    'provider_guid': '{1C95126E-7EEA-49A9-A3FE-A378B03DDB4D}',
    'event_ids': {
        # Event ID 3008 got DNS Queries and DNS Answers. Meaning, that information in ETW will arrive after DNS Response
        # is received and not after DNS Query Request is sent.
        'dns_request_response': 3008
    }
}


# Event Tracing Kernel-Process.
ETW_KERNEL_PROCESS = {
    'provider_name': 'Microsoft-Windows-Kernel-Process',
    'provider_guid': '{22FB2CD6-0E7B-422B-A0C7-2FAD1FD0E716}',
    'event_ids': {
        'process_create': 1  # Emits all the processes that are started.
    }
}


# You need SYSTEM privileges to execute this one. Try with psexec -s -i
ETW_SECURITY_AUDITING = {
    'provider_name': 'Microsoft-Windows-Security-Auditing',
    'provider_guid': '{54849625-5478-4994-A5BA-3E3B0328C30D}',
    'event_ids': {
        'process_create': 4688      # Emits all the processes that are started.
    }
}


ETW_SYSMON = {
    'provider_name': 'Microsoft-Windows-Sysmon',
    'provider_guid': '{5770385F-C22A-43E0-BF4C-06F5698FFBD9}',
    'event_ids': {
        'process_create': 1         # Emits all the processes that are started.
    }
}
