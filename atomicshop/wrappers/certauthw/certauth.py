"""
Original code was taken from: https://github.com/ikreymer/certauth/blob/master/certauth/certauth.py
The script undergone many changes from the original.
"""
import os
from io import BytesIO
from argparse import ArgumentParser
from collections import OrderedDict
import threading

from .. import pyopensslw
from ... import domains, ip_addresses, certificates

from OpenSSL import crypto


ROOT_CA = '!!root_ca'


# =================================================================
# noinspection PyPep8Naming
class CertificateAuthority(object):
    """
    Utility class for signing individual certificate
    with a root cert.

    Static generate_ca_root() method for creating the root cert

    All certs saved on filesystem. Individual certs are stored
    in specified certs_dir and reused if previously created.
    """

    def __init__(self, ca_name,
                 ca_file_cache,
                 cert_cache=None,
                 cert_not_before=0,
                 cert_not_after=certificates.SECONDS_NOT_AFTER_3_YEARS,
                 overwrite=False):

        if isinstance(ca_file_cache, str):
            self.ca_file_cache = RootCACache(ca_file_cache)
        else:
            self.ca_file_cache = ca_file_cache

        if isinstance(cert_cache, str):
            self.cert_cache = FileCache(cert_cache)
        elif isinstance(cert_cache, int):
            self.cert_cache = LRUCache(max_size=cert_cache)
        elif cert_cache is None:
            self.cert_cache = LRUCache(max_size=100)
        else:
            self.cert_cache = cert_cache

        self.ca_name = ca_name

        self.cert_not_before = cert_not_before
        self.cert_not_after = cert_not_after

        res = self.load_root_ca_cert(overwrite=overwrite)
        self.ca_cert, self.ca_key = res

    def load_root_ca_cert(self, overwrite=False):
        cert_str = None

        if not overwrite:
            cert_str = self.ca_file_cache.get(ROOT_CA)

        # if cached, just read pem
        if cert_str:
            cert, key = self.read_pem(BytesIO(cert_str))

        else:
            cert, key = self.generate_ca_root(self.ca_name)

            # Write cert + key
            buff = BytesIO()
            self.write_pem(buff, cert, key)
            cert_str = buff.getvalue()

            # store cert in cache
            self.ca_file_cache[ROOT_CA] = cert_str

        return cert, key

    def load_cert(
            self,
            host,
            certificate=None,
            overwrite=False,
            wildcard=False,
            wildcard_use_parent=False,
            include_cache_key=False,
            cert_ips=None,
            cert_fqdns=None):

        if not cert_ips:
            cert_ips = set()
        if not cert_fqdns:
            cert_fqdns = set()

        # Check if provided host is an IP address.
        is_host_ip = ip_addresses.is_ip_address(host)

        # If host is an IP address, then 'wildcard' definitely will be 'False', since it is only for domains.
        if is_host_ip:
            wildcard = False

        if wildcard and wildcard_use_parent:
            host = domains.get_domain_without_first_subdomain_if_no_subdomain_return_as_is(host)

        # Convert 'set' instance to ordered 'list' instance.
        cert_ips = list(cert_ips)

        # If 'overwrite' wasn't specified, then check if the certificate is already in the cache.
        # None will be returned if not found.
        cert_str = None
        if not overwrite:
            cert_str = self.cert_cache.get(host)

        # If certificate was found in the cache, then read pem from the cache.
        if cert_str:
            cert, key = self.read_pem(BytesIO(cert_str))
        # If not, create new.
        else:
            # if not cached, generate new root or host cert
            cert, key = pyopensslw.generate_server_certificate_ca_signed(
                ca_cert=self.ca_cert,
                ca_key=self.ca_key,
                host=host,
                certificate=certificate,
                wildcard=wildcard,
                is_host_ip=is_host_ip,
                cert_ips=cert_ips,
                cert_fqdns=cert_fqdns,
                seconds_not_before=self.cert_not_before,
                seconds_not_after=self.cert_not_after,
            )

            # Write cert + key
            buff = BytesIO()
            self.write_pem(buff, cert, key)
            cert_str = buff.getvalue()

            # store cert in cache
            self.cert_cache[host] = cert_str

        if not include_cache_key:
            return cert, key
        else:
            cache_key = host
            if hasattr(self.cert_cache, 'key_for_host'):
                cache_key = self.cert_cache.key_for_host(host)

            return cert, key, cache_key

    def cert_for_host(self, host, certificate=None, overwrite=False, wildcard=False, cert_ips=None, cert_fqdns=None):

        if not cert_ips:
            cert_ips = set()
        if not cert_fqdns:
            cert_fqdns = set()

        res = self.load_cert(host,
                             certificate=certificate,
                             overwrite=overwrite,
                             wildcard=wildcard,
                             wildcard_use_parent=False,
                             include_cache_key=True,
                             cert_ips=cert_ips,
                             cert_fqdns=cert_fqdns)

        return res[2]

    def get_wildcard_cert(self, cert_host, overwrite=False):
        res = self.load_cert(
            cert_host, overwrite=overwrite, wildcard=True, wildcard_use_parent=True, include_cache_key=True)

        return res[2]

    def get_root_PKCS12(self):
        p12 = crypto.PKCS12()
        p12.set_certificate(self.ca_cert)
        p12.set_privatekey(self.ca_key)
        return p12.export()

    def get_root_pem(self):
        return self.ca_file_cache.get(ROOT_CA)

    def get_root_pem_filename(self):
        return self.ca_file_cache.ca_file

    def generate_ca_root(self, ca_name, hash_algo: str = 'sha256'):
        # Generate key
        key = pyopensslw.generate_private_key()

        # Generate cert
        cert = pyopensslw.generate_server_certificate_empty(ca_name, self.cert_not_before, self.cert_not_after)

        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(key)
        cert.add_extensions([
            crypto.X509Extension(b"basicConstraints",
                                 True,
                                 b"CA:TRUE, pathlen:0"),

            crypto.X509Extension(b"keyUsage",
                                 True,
                                 b"keyCertSign, cRLSign"),

            crypto.X509Extension(b"subjectKeyIdentifier",
                                 False,
                                 b"hash",
                                 subject=cert),
            ])
        cert.sign(key, hash_algo)

        return cert, key

    @staticmethod
    def write_pem(buff, cert, key):
        buff.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))
        buff.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))

    @staticmethod
    def read_pem(buff):
        cert = crypto.load_certificate(crypto.FILETYPE_PEM, buff.read())
        buff.seek(0)
        key = crypto.load_privatekey(crypto.FILETYPE_PEM, buff.read())
        return cert, key


# =================================================================
class FileCache(object):
    def __init__(self, certs_dir):
        self._lock = threading.Lock()
        self.certs_dir = certs_dir
        self.modified = False

        if self.certs_dir and not os.path.exists(self.certs_dir):
            os.makedirs(self.certs_dir)

    def key_for_host(self, host):
        host = host.replace(':', '-')
        return os.path.join(self.certs_dir, host) + '.pem'

    def __setitem__(self, host, cert_string):
        filename = self.key_for_host(host)
        with self._lock:
            with open(filename, 'wb') as fh:
                fh.write(cert_string)
                self.modified = True

    def get(self, host):
        filename = self.key_for_host(host)

        try:
            with open(filename, 'rb') as fh:
                return fh.read()
        except FileNotFoundError:
            return b''


# =================================================================
class RootCACache(FileCache):
    def __init__(self, ca_file):
        self.ca_file = ca_file
        ca_dir = os.path.dirname(ca_file) or '.'
        super(RootCACache, self).__init__(ca_dir)

    def key_for_host(self, host=None):
        return self.ca_file


# =================================================================
class LRUCache(OrderedDict):
    def __init__(self, max_size):
        super(LRUCache, self).__init__()
        self.max_size = max_size

    def __setitem__(self, host, cert_string):
        super(LRUCache, self).__setitem__(host, cert_string)
        if len(self) > self.max_size:
            self.popitem(last=False)


# =================================================================
def main(args=None):
    parser = ArgumentParser(description='Certificate Authority Cert Maker Tools')

    parser.add_argument('root_ca_cert',
                        help='Path to existing or new root CA file')

    parser.add_argument('-c', '--certname', action='store',
                        help='Name for root certificate')

    parser.add_argument('-n', '--hostname',
                        help='Hostname certificate to create')

    parser.add_argument('-d', '--certs-dir',
                        help='Directory for host certificates')

    parser.add_argument('-f', '--force', action='store_true',
                        help='Overwrite certificates if they already exist')

    parser.add_argument('-w', '--wildcard_cert', action='store_true',
                        help='add wildcard SAN to host: *.<host>, <host>')

    parser.add_argument('-I', '--cert_ips', action='store', default='',
                        help='add IPs to the cert\'s SAN')

    parser.add_argument('-D', '--cert_fqdns', action='store', default='',
                        help='add more domains to the cert\'s SAN')

    r = parser.parse_args(args=args)

    certs_dir = r.certs_dir
    wildcard = r.wildcard_cert

    root_cert = r.root_ca_cert
    hostname = r.hostname

    if r.cert_ips != '':
        cert_ips = r.cert_ips.split(',')
    else:
        cert_ips = []
    if r.cert_fqdns != '':
        cert_fqdns = r.cert_fqdns.split(',')
    else:
        cert_fqdns = []

    if not hostname:
        overwrite = r.force
    else:
        overwrite = False

    cert_cache = FileCache(certs_dir)
    ca_file_cache = RootCACache(root_cert)

    ca = CertificateAuthority(ca_name=r.certname,
                              ca_file_cache=ca_file_cache,
                              cert_cache=cert_cache,
                              overwrite=overwrite)

    # Just creating the root cert
    if not hostname:
        if ca_file_cache.modified:
            print('Created new root cert: "' + root_cert + '"')
            return 0
        else:
            print('Root cert "' + root_cert +
                  '" already exists,' + ' use -f to overwrite')
            return 1

    # Sign a certificate for a given host
    overwrite = r.force
    ca.load_cert(
        hostname,
        overwrite=overwrite,
        wildcard=wildcard,
        wildcard_use_parent=False,
        cert_ips=cert_ips,
        cert_fqdns=cert_fqdns)

    if cert_cache.modified:
        print('Created new cert "' + hostname +
              '" signed by root cert ' +
              root_cert)
        return 0

    else:
        print('Cert for "' + hostname + '" already exists,' +
              ' use -f to overwrite')
        return 1


# pragma: no cover
if __name__ == "__main__":
    main()
