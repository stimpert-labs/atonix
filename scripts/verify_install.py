# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""Post-install smoke test for the ``atonix`` package.

This script verifies that an installed build of ``atonix`` is wired up
correctly. It:

1. Imports the package and its ``cryptography`` runtime dependency.
2. Generates a throwaway RSA key (no network or real credentials used).
3. Instantiates :class:`atonix.AtonixClient` with a dummy API key and
   confirms the ``assets``, ``issues``, ``models``, and ``process_data``
   resource attributes are initialized.

It is intended to be run after building or installing the wheel, e.g.::

    uv run python scripts/verify_install.py

The script exits with a non-zero status if any step fails, making it
suitable for use as a manual sanity check or in a CI smoke-test step.
See ``BUILD.md`` for context.
"""

import sys

try:
    from cryptography.hazmat.primitives.asymmetric import rsa

    from atonix import AtonixClient

    print("Imports successful.")
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)

# Generate dummy key
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)

try:
    client = AtonixClient("dummy-api-key", private_key)
    print("Client instantiated.")

    assert client.assets is not None
    assert client.issues is not None
    assert client.models is not None
    assert client.process_data is not None
    print("Resources initialized.")

except Exception as e:
    print(f"Instantiation failed: {e}")
    sys.exit(1)

print("Verification complete.")
