import sys
import os
import tempfile
import subprocess
import re
import base64
import textwrap


LINUX_CA_DIR: str = '/usr/local/share/ca-certificates'


def _linux_cert_path(issuer_name: str) -> str:
    return f'{LINUX_CA_DIR}/{issuer_name}.crt'


def _run_sudo(command: list[str], sudo_password: str, **kwargs) -> subprocess.CompletedProcess:
    """Run a command with sudo -S, piping the password via stdin."""
    return subprocess.run(
        ['sudo', '-S'] + command,
        input=sudo_password + '\n',
        capture_output=True,
        text=True,
        **kwargs
    )


def is_ca_installed(issuer_name: str) -> tuple[bool, str]:
    if sys.platform == 'win32':
        result = subprocess.run(
            ['certutil', '-store', 'Root', issuer_name],
            capture_output=True,
            text=True,
        )

        if 'Object was not found' in result.stdout:
            return False, ''

        if result.returncode == 0:
            return True, ''
        else:
            message: str = (f"stdout: {result.stdout}\n"
                            f"stderr: {result.stderr}\n")
            return False, message
    elif sys.platform == 'linux':
        cert_path: str = _linux_cert_path(issuer_name)
        return os.path.isfile(cert_path), ''
    else:
        return False, f"Unsupported platform: {sys.platform}"


def remove_ca_certificate(issuer_name: str, sudo_password: str = None) -> int:
    if sys.platform == 'win32':
        result = subprocess.run(
            ['certutil', '-delstore', 'Root', issuer_name],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"Error removing certificate: {result.stderr}", file=sys.stderr)
            return 1
    elif sys.platform == 'linux':
        cert_path: str = _linux_cert_path(issuer_name)
        result = _run_sudo(['rm', '-f', cert_path], sudo_password)
        if result.returncode != 0:
            print(f"Error removing certificate: {result.stderr}", file=sys.stderr)
            return 1

        result = _run_sudo(['update-ca-certificates', '--fresh'], sudo_password)
        if result.returncode != 0:
            print(f"Error updating CA certificates: {result.stderr}", file=sys.stderr)
            return 1
    else:
        print(f"Unsupported platform: {sys.platform}", file=sys.stderr)
        return 1

    return 0


def install_ca_certificate(certificate_string: str, issuer_name: str = None, sudo_password: str = None) -> int:
    pem = certificate_string or ""

    # Extract one or more CERTIFICATE blocks
    blocks = re.findall(
        r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
        pem,
        flags=re.DOTALL,
    )
    if not blocks:
        print("Error installing certificate: no PEM CERTIFICATE block found.", file=sys.stderr)
        return 1

    def normalize_pem(block: str, line_ending: str = "\r\n") -> str:
        m = re.search(
            r"-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----",
            block,
            flags=re.DOTALL,
        )
        if not m:
            raise ValueError("Invalid PEM block.")

        # Remove everything except Base64 alphabet and padding
        b64 = re.sub(r"[^A-Za-z0-9+/=]", "", m.group(1))

        # Strict decode/encode round-trip to ensure it is valid DER
        der = base64.b64decode(b64, validate=True)
        b64_clean = base64.b64encode(der).decode("ascii")
        wrapped = line_ending.join(textwrap.wrap(b64_clean, 64))

        return (
            f"-----BEGIN CERTIFICATE-----{line_ending}"
            + wrapped
            + f"{line_ending}-----END CERTIFICATE-----{line_ending}"
        )

    if sys.platform == 'win32':
        for block in blocks:
            tmp_path = None
            try:
                normalized = normalize_pem(block, line_ending="\r\n")

                with tempfile.NamedTemporaryFile(
                    mode="w",
                    suffix=".cer",
                    delete=False,       # certutil needs a real path on Windows
                    encoding="ascii",
                    newline="",
                ) as f:
                    f.write(normalized)
                    tmp_path = f.name

                result = subprocess.run(
                    ["certutil", "-f", "-addstore", "Root", tmp_path],
                    text=True,
                    capture_output=True,
                )

                if result.returncode != 0:
                    dump = subprocess.run(
                        ["certutil", "-dump", tmp_path],
                        text=True,
                        capture_output=True,
                    )

                    print(
                        "Error installing certificate:\n"
                        f"stdout: {result.stdout}\n"
                        f"stderr: {result.stderr}\n"
                        "certutil -dump output:\n"
                        f"{dump.stdout}\n"
                        f"{dump.stderr}",
                        file=sys.stderr,
                    )
                    return 1

            except Exception as e:
                print(f"Error installing certificate: {e}", file=sys.stderr)
                return 1

            finally:
                if tmp_path:
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

    elif sys.platform == 'linux':
        if not issuer_name:
            print("Error: issuer_name is required on Linux for certificate file naming.", file=sys.stderr)
            return 1

        cert_path: str = _linux_cert_path(issuer_name)
        try:
            # Concatenate all PEM blocks into a single string.
            normalized_blocks: list[str] = [normalize_pem(block, line_ending="\n") for block in blocks]
            pem_content: str = "".join(normalized_blocks)

            # Use 'sudo tee' to write to the protected directory.
            # sudo -S reads the password from stdin; we prepend it before the PEM content.
            result = subprocess.run(
                ['sudo', '-S', 'tee', cert_path],
                input=sudo_password + '\n' + pem_content,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"Error writing certificate file: {result.stderr}", file=sys.stderr)
                return 1
        except Exception as e:
            print(f"Error writing certificate file: {e}", file=sys.stderr)
            return 1

        result = _run_sudo(['update-ca-certificates'], sudo_password)
        if result.returncode != 0:
            print(
                "Error installing certificate:\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}",
                file=sys.stderr,
            )
            return 1
    else:
        print(f"Unsupported platform: {sys.platform}", file=sys.stderr)
        return 1

    return 0


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: install_ca_certificate.py <Issuer Name> <crt cert string> [sudo_password]", file=sys.stderr)
        return 1

    certificate_string_base64: str = sys.argv[2]
    certificate_string = base64.b64decode(certificate_string_base64).decode("utf-8")
    if not "-----BEGIN CERTIFICATE-----" in certificate_string:
        print("Error: Certificate string must be in PEM format.", file=sys.stderr)
        print(certificate_string, file=sys.stderr)
        return 1

    issuer_name: str = sys.argv[1]
    sudo_password: str | None = sys.argv[3] if len(sys.argv) > 3 else None

    is_installed, message = is_ca_installed(issuer_name)
    if not is_installed and message:
        print(f"Error checking certificate installation: {message}", file=sys.stderr)
        return 1

    if is_installed:
        rc: int = remove_ca_certificate(issuer_name, sudo_password=sudo_password)
        if rc != 0:
            return rc

    rc: int = install_ca_certificate(certificate_string, issuer_name=issuer_name, sudo_password=sudo_password)
    if rc != 0:
        return rc

    is_installed, message = is_ca_installed(issuer_name)
    if not is_installed and message:
        print(f"Error checking certificate installation: {message}", file=sys.stderr)
        return 1

    if not is_installed:
        print("Error: Certificate installation failed.", file=sys.stderr)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())