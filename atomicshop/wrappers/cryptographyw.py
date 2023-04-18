from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa


"""
It is no longer a requirement to use 'backend' keyword argument.
"""


def convert_pem_to_x509_certificate_object(certificate):
    """Convert PEM certificate to x509 object.

    :param certificate: string or bytes - certificate to convert.
    :return: certificate in x509 object of 'cryptography' module.
    """

    # If certificate was passed as PEM string, we'll convert it to bytes, since that what 'load_pem_x509_certificate'
    # expects.
    if isinstance(certificate, str):
        certificate = certificate.encode()

    return x509.load_pem_x509_certificate(certificate)


def convert_der_to_x509_certificate_object(certificate: bytes):
    """Convert DER certificate from socket to x509 object.

    :param certificate: bytes, certificate to convert.
    :return: certificate in x509 object of 'cryptography' module.
    """

    return x509.load_der_x509_certificate(certificate)


def generate_private_key(bits: int = 2048):
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=bits
    )

    return private_key


def _get_extensions_properties(certificate):
    # Currently here for reference.
    for ext in certificate.extensions:
        # if skip_extensions and ext.oid._name in skip_extensions:
        #     continue

        try:
            sub_keys = [x._name for x in ext.value or []]
        # If there are no sub-keys, we'll get TypeError, object is not iterable.
        except TypeError:
            sub_keys = []
        # Not all sub keys have '_name' attribute.
        except AttributeError:
            sub_keys = []

        if not sub_keys:
            sub_keys = vars(ext._value)

        print(f'{ext.oid._name}: {sub_keys}')


"""
def _testing_references():
    x509.NameOID.COMMON_NAME

    from cryptography.x509.oid import ObjectIdentifier
    ObjectIdentifier('2.5.4.3')

    import ssl
    ssl._txt2obj(x509.NameOID.COMMON_NAME.dotted_string)
    # NID, short name, long name, OID

    extended_key_usage = x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH])


def convert_certificate_to_dict(certificate):
    def to_dict(obj):
        def get_keys(obj):
            keys = list()
            for key in dir(obj):
                if not key.startswith('__'):
                    keys.append(key)
            return keys

        # if isinstance(obj, dict):

        if not (hasattr(obj, "__dict__") or isinstance(obj, dict) or isinstance(obj, list)):
            test_dict = obj
        elif isinstance(obj, list):
            test_dict = []
            for item in obj:
                test_dict.append(to_dict(item))
        # elif \
        #         isinstance(obj, x509.Extension) or \
        #         isinstance(obj, x509.Extensions) or \
        #         isinstance(obj, x509.BasicConstraints):
        #     test_dict = vars(obj)
        #     for key, value in test_dict.items():
        #         test_dict[key] = to_dict(value)
        # elif isinstance(obj, x509.ObjectIdentifier):
        #     keys = dir(obj)
        #     test_dict = dict()
        #
        #     for key in keys:
        #         if not key.startswith('__'):
        #             test_dict[key] = getattr(obj, key)
        else:
            try:
                test_dict = vars(obj)
                for key, value in test_dict.items():
                    test_dict[key] = to_dict(value)
            except TypeError:
                # if not (isinstance(obj, str) or isinstance(obj, int) or isinstance(obj, bool)):
                keys = get_keys(obj)

                test_dict = dict()
                for key in keys:
                    value = getattr(obj, key)
                    if hasattr(value,"__dict__") or isinstance(value, dict) or isinstance(value, list):
                        test_dict[key] = to_dict(value)
                    else:
                        test_dict[key] = value
                # else:
                #     test_dict = obj


        return test_dict
    # test = dict()

    # test = vars(certificate.extensions)
    # test = certificate.extensions
    test = to_dict(certificate)
    print(test)


    # for ext in certificate.extensions:
    #     try:
    #         for single_value in ext.value:
    #             print(single_value)
    #     except TypeError:
    #         test.update(vars(ext))
"""


def copy_extensions_from_certificate_to_new_certificate(certificate, skip_extensions: list = None):
    """Copy extensions from one certificate to another.

    :param certificate: certificate to copy extensions from.
    :param skip_extensions: list of extensions to skip.
    :return: new certificate with copied extensions.
    """

    # Builder is the new certificate.
    builder = x509.CertificateBuilder()
    builder = builder.subject_name(certificate.subject)
    builder = builder.issuer_name(certificate.issuer)
    builder = builder.not_valid_before(certificate.not_valid_before)
    builder = builder.not_valid_after(certificate.not_valid_after)
    builder = builder.serial_number(certificate.serial_number)
    builder = builder.public_key(certificate.public_key())

    for ext in certificate.extensions:
        if skip_extensions and ext.oid._name in skip_extensions:
            continue

        builder = builder.add_extension(
            ext.value, critical=ext.critical
        )

    # new_cert = builder.sign(
    #     private_key=private_key, algorithm=cert.signature_hash_algorithm
    # )
