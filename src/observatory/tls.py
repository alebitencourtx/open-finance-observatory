"""Public ICP-Brasil root, scoped to the Bradesco transport; no TLS bypass."""
import hashlib
from pathlib import Path
import ssl

import truststore

ROOT_SHA256 = '6e0bff069a26994c15de2c4888cc54af84882e5495b7fbf66be9ccffec7489f6'


def bradesco_context():
    certificate = Path(__file__).parent / 'certificates/icp-brasil-v10.pem'
    pem = certificate.read_text(encoding='ascii')
    if hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest() != ROOT_SHA256:
        raise ValueError('Fingerprint da raiz ICP-Brasil divergente')
    context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cadata=pem)
    return context
