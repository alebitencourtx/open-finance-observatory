import ssl

from observatory.tls import bradesco_context


def test_scoped_public_root_keeps_certificate_and_hostname_verification():
    context = bradesco_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname
