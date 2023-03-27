# Defining Dictionary of Numeric to String DNS Query Types.
TYPES_DICT = {
    '1': 'A',
    '2': 'NS',
    '5': 'CNAME',
    '12': 'PTR',
    '28': 'AAAA',
    '33': 'SRV'
}

# Event Tracing DNS info.
ETW_DNS_INFO = {
    'provider_name': 'Microsoft-Windows-DNS-Client',
    'provider_guid': '{1C95126E-7EEA-49A9-A3FE-A378B03DDB4D}',
    # Event ID 3008 got DNS Queries and DNS Answers. Meaning, that information in ETW will arrive after DNS Response
    # is received and not After DNS Query is sent.
    'event_id': 3008
}
