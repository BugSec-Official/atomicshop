import tldextract


def get_domain_without_first_subdomain_if_no_subdomain_return_as_is(
        host: str, offline_tld_database: bool = True) -> str:
    """
    The function returns domain without the first subdomain.
        Example: sub1.sub2.main.com
        Result: sub2.main.com
    If it is already the main domain then it will return as is.
        Example: main.com
        Result: main.com

    The function is stripped from 'certauth' library to override 'tldextract' behavior of going online and to fetch
    the list of known tlds.

    :param host: the domain.
    :param offline_tld_database: if True, the function will use 'tldextract' offline database. If False, it will go
        online and fetch the list of known tlds.
    :return:
    """

    # Split the domain to 2 parts: the most left until the first '.' character, and the right part after the first '.'.
    host_parts = host.split('.', 1)
    # If there are less than 2 elements in 'hosts_parts' or there is no '.' in the second part, it means that 'host'
    # is already the main parent domain.
    if len(host_parts) < 2 or '.' not in host_parts[1]:
        return host

    if offline_tld_database:
        # Extract main domain, subdomains and suffix from passed 'host'.
        # Documented way of using 'tldextract' module without HTTP fetching.
        extracted_domain_parts = tldextract.TLDExtract(suffix_list_urls=str())(host)
    else:
        extracted_domain_parts = tldextract.extract(host)

    # allow using parent domain if:
    # 1) no suffix (unknown tld)
    # 2) the parent domain contains 'domain.suffix', not just .suffix
    if not extracted_domain_parts.suffix or \
            extracted_domain_parts.domain + '.' + extracted_domain_parts.suffix in host_parts[1]:
        return host_parts[1]

    return host


def get_registered_domain(domain: str) -> str:
    """
    The function will return only the main domain.
        Example: sub1.sub2.main.com
        Return: main.com
    If there is no tld or tld is not in 'tldextract' offline database, the input domain will be returned as is.
        Example: some-domain-without-tld
        Return: some-domain-without-tld
    :param domain: string of domain to process.
    :return: string of main registered domain with tld only.
    """
    # Extract all the parts from domain with 'tldextract'.
    extracted_domain_parts = tldextract.TLDExtract(suffix_list_urls=str())(domain)

    # If 'suffix' is empty, it means that the tld is not in 'tldextract' offline database or there is no tld at all,
    # for example: some-domain-without-tld
    if not extracted_domain_parts.suffix:
        return domain
    else:
        return f'{extracted_domain_parts.registered_domain}.{extracted_domain_parts.suffix}'
