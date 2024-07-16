from ..wrappers.ctyping.etw_winapi import etw_functions


def get_providers():
    return etw_functions.get_all_providers()
