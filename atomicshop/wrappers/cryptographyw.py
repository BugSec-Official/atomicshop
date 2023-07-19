from ..print_api import print_api

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from OpenSSL import crypto


"""
It is no longer a requirement to use 'backend' keyword argument.
https://cryptography.io/en/latest/faq/#what-happened-to-the-backend-argument
"""


OID_TO_BUILDER_CLASS_EXTENSION_NAME: dict = {
    '2.5.29.37': 'ExtendedKeyUsage'
}


def convert_pem_to_x509_object(certificate):
    """Convert PEM certificate to x509 object.

    :param certificate: string or bytes - certificate to convert.
    :return: certificate in x509 object of 'cryptography' module.
    """

    # If certificate was passed as PEM string, we'll convert it to bytes, since that what 'load_pem_x509_certificate'
    # expects.
    if isinstance(certificate, str):
        certificate = certificate.encode()

    return x509.load_pem_x509_certificate(certificate)


def convert_der_to_x509_object(certificate: bytes):
    """Convert DER certificate from socket to x509 object.

    :param certificate: bytes, certificate to convert.
    :return: certificate in x509 object of 'cryptography' module.
    """

    return x509.load_der_x509_certificate(certificate)


def convert_x509_object_to_pem_bytes(certificate) -> bytes:
    """Convert x509 object to PEM certificate.
    :param certificate: certificate in x509 object of 'cryptography' module.
    :return: string or bytes of certificate in PEM byte string format.
    """

    return certificate.public_bytes(serialization.Encoding.PEM)


def generate_private_key(public_exponent: int = 65537, bits: int = 2048):
    private_key = rsa.generate_private_key(
        public_exponent=public_exponent,
        key_size=bits
    )

    return private_key


def copy_extensions_from_old_cert_to_new_cert(
        certificate, skip_extensions: list = None, use_extension_names: bool = False, **kwargs):
    """Copy extensions from one certificate to another.

    Python's cryptography module doesn't provide a method to remove extensions from certificate.
    So we're using this workaround to copy extensions from one certificate to another, while skipping some of them
    from the specified 'skip_extensions' list.

    Currently, the function skipping the highest hierarchy extensions, like 'X509v3 Subject Alternative Name',
    'X509v3 Basic Constraints', etc. It is skipping the extensions that are inside the highest hierarchy extensions
    only that are iterable, like 'Extended Key Usage'. For example if you provide OID of
    'TLS Web Server Authentication', it will be skipped.
    In addition to its experimental state, only 'Extended Key Usage' extension is supported for now.

    :param certificate: x509 certificate object of cryptography module to copy extensions from.
    :param skip_extensions: list of strings of OIDs in "dotted_string" format of extensions to skip.
    :param use_extension_names: boolean, if True, "skip_extensions" will be treated as extension names, not OIDs.
        Since the easiest place to find the extension name was in "extension.oid._name" and "_name" is a private field,
        this option is False by default. The official documentation doesn't support extension names, since there is
        no standard for them. They may be different from application to application. So we're using the ones that are
        provided with cryptography module. This is highly advised not to use this option, unless you know what you're
        doing.
    :return: new x509 certificate object of cryptography module with copied extensions and old public key.
    """

    # We need to generate a new private key, since we can't use the old one to sign the new certificate.
    new_private_key = generate_private_key()

    # Builder is the new certificate. We will add all the informational data from the old certificate to it.
    builder = x509.CertificateBuilder()
    builder = builder.subject_name(certificate.subject)
    builder = builder.issuer_name(certificate.issuer)
    builder = builder.not_valid_before(certificate.not_valid_before)
    builder = builder.not_valid_after(certificate.not_valid_after)
    builder = builder.serial_number(certificate.serial_number)

    # We're using the new private key that we will sign with the new certificate later.
    builder = builder.public_key(new_private_key.public_key())
    # In case you want to use the old one.
    # builder = builder.public_key(certificate.public_key())

    # Iterate through all the extensions of the old certificate.
    for old_extension in certificate.extensions:
        # If the list of extensions to skip 'skip_extensions' is provided.
        if skip_extensions:
            # We'll check if the current extension is in the list of extensions to skip.

            # If 'use_extension_names' is false, we'll use the 'dotted_string' of the extension.
            if not use_extension_names and old_extension.oid.dotted_string in skip_extensions:
                # If it is, we'll skip it.
                message = f'Skipping certificate extension OID: {old_extension.oid.dotted_string}.'
                print_api(message, **kwargs)
                continue
            # If 'use_extension_names' is true, we'll use the '_name' of the extension.
            elif use_extension_names and old_extension.oid._name in skip_extensions:
                message = f'Skipping certificate extension: {old_extension.oid._name}.'
                print_api(message, **kwargs)
                continue

            # We'll try to iterate through the sub-keys of the current extension.
            try:
                # Iterate through all the sub-keys /usages of the current extension.
                # If the 'dotted_string' of the current sub-key is in the list of extensions to skip,
                # we'll skip it. Return only the list of not skipped usages.
                new_usages: list = list()
                for usage in old_extension.value:
                    # If 'use_extension_names' is false, we'll use the 'dotted_string' of the extension.
                    if not use_extension_names and usage.dotted_string in skip_extensions:
                        message = f'Skipping certificate extension OID: {usage.dotted_string}.'
                        print_api(message, **kwargs)
                        continue
                    # If 'use_extension_names' is true, we'll use the '_name' of the extension.
                    elif use_extension_names and usage._name in skip_extensions:
                        message = f'Skipping certificate extension: {usage._name}.'
                        print_api(message, **kwargs)
                        continue

                    new_usages.append(usage)

                # Only add the extension if there are any usages left.
                if new_usages:
                    # Get the class name of X509 module that corresponds to the current extension OID.
                    builder_class = OID_TO_BUILDER_CLASS_EXTENSION_NAME[old_extension.oid.dotted_string]
                    # Add the extension to the new certificate by the extension class name string of the x509 module.
                    builder = builder.add_extension(
                        getattr(x509, builder_class)(new_usages), critical=old_extension.critical)
            # If there are no sub-keys / usages of the current extension, we'll get TypeError, object is not iterable.
            # If there is no 'dotted_string' attribute in the OID object of the current extension,
            # we'll get AttributeError.
            except (TypeError, AttributeError):
                # Add the extension as is.
                builder = builder.add_extension(old_extension.value, critical=old_extension.critical)

        # If the list of extensions to skip 'skip_extensions' is not provided.
        else:
            # Add the extension as is.
            builder = builder.add_extension(old_extension.value, critical=old_extension.critical)

    # Sign the new certificate.
    new_cert = builder.sign(private_key=new_private_key, algorithm=hashes.SHA256())

    return new_cert, new_private_key


def _get_extensions_properties(certificate):
    # Currently here for reference.
    # Can show all the extensions and their sub-keys.

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