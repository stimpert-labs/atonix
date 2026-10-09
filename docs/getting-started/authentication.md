# Authentication

Every request is signed with your RSA private key and carries your API key. The client handles
signing; you only need to tell it where the credentials are.

## API key

Pass `api_key=...` to the client, or set `ATONIX_API_KEY`.

## Private key

The client looks for the private key in this order and uses the first one it finds:

1. The `private_key` argument, an already-loaded `cryptography` key object.
2. `ATONIX_PRIVATE_KEY`, the PEM contents.
3. `ATONIX_PRIVATE_KEY_PATH`, a path to the PEM file.

### Load the key yourself

Use this when the key comes from a secrets manager or somewhere other than a file. Decrypt it
when you load it, and don't pass a password to the client.

```python
from cryptography.hazmat.primitives import serialization

from atonix import AtonixClient

with open("path/to/private_key.pem", "rb") as f:
    private_key = serialization.load_pem_private_key(
        f.read(),
        password=b"your-password",  # or None for an unencrypted key
    )

client = AtonixClient(api_key="YOUR_API_KEY", private_key=private_key)
```

### Key file path

```bash
export ATONIX_PRIVATE_KEY_PATH=/path/to/private_key.pem
export ATONIX_PRIVATE_KEY_PASSWORD=your-password  # only if encrypted
```

```python
client = AtonixClient(api_key="YOUR_API_KEY")
```

There's no `private_key_path` argument; the environment variable is the only way to give a path.

### PEM contents in the environment

Handy in containers and CI, where secrets are injected as variables. Literal `\n` sequences are
converted to newlines.

```bash
export ATONIX_PRIVATE_KEY="$(cat /path/to/private_key.pem)"
```

!!! note
    `ATONIX_PRIVATE_KEY` wins over `ATONIX_PRIVATE_KEY_PATH`. Don't set both.

### Encrypted keys

For a key loaded from the environment, give the password with the `private_key_password`
argument or `ATONIX_PRIVATE_KEY_PASSWORD`.

## Environment variables

| Variable                      | Purpose                                                                         |
| ----------------------------- | ------------------------------------------------------------------------------- |
| `ATONIX_API_KEY`              | API key, used when `api_key` isn't passed.                                      |
| `ATONIX_PRIVATE_KEY`          | PEM contents. Takes precedence over `ATONIX_PRIVATE_KEY_PATH`.                  |
| `ATONIX_PRIVATE_KEY_PATH`     | Path to the PEM file.                                                           |
| `ATONIX_PRIVATE_KEY_PASSWORD` | Password for an encrypted key (optional).                                       |
| `ATONIX_LOG_PAYLOADS`         | `1`/`true`/`yes`/`on` logs full time-series payloads at DEBUG. Off by default.  |

With everything set, construction is just `AtonixClient()`.

## Other client options

| Argument      | Default                  | Description                                                                 |
| ------------- | ------------------------ | --------------------------------------------------------------------------- |
| `environment` | `AtonixEnvironment.US`   | An [`AtonixEnvironment`][atonix.AtonixEnvironment] (`US`, `INDIA`) or a custom base URL. |
| `timeout`     | `30.0`                   | Per-request timeout in seconds.                                             |
| `max_retries` | `3`                      | Retries for 429 and 5xx responses.                                          |
| `allow_insecure` | `False`               | Allow a plain `http://` custom URL (local testing only). By default only `https://` is accepted. |

```python
from atonix import AtonixClient, AtonixEnvironment

client = AtonixClient(environment=AtonixEnvironment.INDIA, timeout=60, max_retries=5)
```

## Clock synchronization

Each signature includes a millisecond UTC timestamp, and the server rejects requests whose
timestamp is too far from its own clock. Keep the host's clock synced with NTP (`chrony`,
`ntpd`, `w32tm`, or your platform's time service).

A skewed clock shows up as an [`AuthenticationError`][atonix.AuthenticationError]. This happens
often on suspended VMs and containers with stale clocks. When the client sees signs of skew,
such as skew-related wording in the error or a server `Date` header more than 60 seconds off, it
adds a hint to the error message.

The client doesn't correct the timestamp from server time, because that would defeat the replay
protection the timestamp provides.
