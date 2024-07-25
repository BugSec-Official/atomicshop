from typing import Literal

from ..wrappers.ctyping.etw_winapi import etw_functions


def get_providers(key_as: Literal['name', 'guid'] = 'name'):
    return etw_functions.get_all_providers(key_as=key_as)


def get_provider_guid_by_name(provider_name):
    providers = get_providers(key_as='name')

    try:
        provider_guid = providers[provider_name]
    except KeyError:
        provider_guid = None

    if not provider_guid:
        raise ValueError(f"Provider '{provider_name}' not found")

    return provider_guid
