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
| `max_retries` | `3`                      | Max attempts per request for 429, 5xx, and network errors (min. 1 attempt). |
| `allow_insecure` | `False`               | Allow a plain `http://` custom URL (local testing only). By default only `https://` is accepted. |
| `verify`      | `True`                   | TLS server verification: `True`, a CA bundle path, an `ssl.SSLContext`, or `False`. See [TLS](#tls). |
| `cert`        | `None`                   | Client certificate for mutual TLS. See [TLS](#tls).                         |
| `proxy`       | `None`                   | Proxy URL or `httpx.Proxy`. See [Proxies](#proxies).                        |
| `headers`     | `None`                   | Extra headers sent with every request, such as `User-Agent`.                |
| `httpx_kwargs`| `None`                   | Any other `httpx.Client` arguments. See [Other httpx options](#other-httpx-options). |

```python
from atonix import AtonixClient, AtonixEnvironment

client = AtonixClient(environment=AtonixEnvironment.INDIA, timeout=60, max_retries=5)
```

## TLS

By default the client verifies the server against the certifi CA bundle, or against
`SSL_CERT_FILE` / `SSL_CERT_DIR` when those are set. Use `verify` to change that.

If you're behind a corporate proxy that re-signs HTTPS traffic, trust its root CA:

```python
client = AtonixClient(verify="/etc/ssl/certs/corp-root-ca.pem")  # a CA file or a directory of CAs
```

For full control, such as trusting only a specific certificate or setting a minimum TLS version,
pass your own `ssl.SSLContext`. The client uses it exactly as given:

```python
import ssl

ctx = ssl.create_default_context(cafile="/path/to/pinned-ca.pem")
ctx.minimum_version = ssl.TLSVersion.TLSv1_3
client = AtonixClient(verify=ctx)
```

For mutual TLS, pass `cert` as a PEM file with both certificate and key, as
`(certfile, keyfile)`, or as `(certfile, keyfile, password)`. If you pass an `ssl.SSLContext`,
load the certificate into it with `ctx.load_cert_chain(...)` instead; combining the two raises
`ValueError`.

`verify=False` turns off certificate checks entirely. Use it only for local debugging: it
leaves your signed requests open to interception.

The same options work on `AsyncAtonixClient`.

## Proxies

The client uses the standard proxy environment variables (`HTTPS_PROXY`, `HTTP_PROXY`,
`ALL_PROXY`, and `NO_PROXY`), and on Windows and macOS falls back to the system proxy settings, so
often there's nothing to configure. To set a proxy in code, use `proxy`. It overrides the
environment:

```python
client = AtonixClient(proxy="http://proxy.corp:8080")
client = AtonixClient(proxy="http://user:password@proxy.corp:8080")  # with proxy credentials
```

If the proxy re-signs HTTPS traffic, also pass its root CA as `verify` (see [TLS](#tls)). The
`verify` and `cert` settings apply to connections through the proxy too.

To ignore the environment and system proxy settings, pass `httpx_kwargs={"trust_env": False}`. This also makes
the client ignore `SSL_CERT_FILE` and `SSL_CERT_DIR`.

## Default headers

`headers` adds headers to every request, for example to identify your application:

```python
client = AtonixClient(headers={"User-Agent": "plant-dashboard/2.1"})
```

Headers passed to a single call (`client.get(..., headers=...)`) take precedence over these.
The Atonix auth headers are always set by the client and can't be replaced this way.

## Other httpx options

`httpx_kwargs` passes any other argument straight to the underlying `httpx.Client` (or
`httpx.AsyncClient`): connection `limits`, `http2=True` (needs the `h2` package),
`event_hooks`, `mounts`, a custom `transport`, and so on.

```python
import httpx

client = AtonixClient(
    httpx_kwargs={
        "limits": httpx.Limits(max_connections=20),
        "event_hooks": {"request": [lambda request: print(request.method, request.url)]},
    }
)
```

Options the client takes by name (`timeout`, `verify`, `cert`, `proxy`, `headers`) can't go in
`httpx_kwargs`; that raises `ValueError`. A custom `transport` replaces httpx's own, so `verify`,
`cert`, and `proxy` no longer apply to it.

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
