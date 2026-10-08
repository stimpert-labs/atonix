# Security Policy

## Supported Versions

`atonix` is a volunteer-maintained project. Only the latest minor release receives security fixes,
on a best-effort basis.

| Version  | Supported |
| -------- | --------- |
| 0.5.x    | ✅        |
| < 0.5    | ❌        |

## Reporting a Vulnerability

**Please do not file a public GitHub issue for security vulnerabilities.**

Instead, report them privately using GitHub's
[Private Vulnerability Reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
feature on this repository:

1. Navigate to the repository's **Security** tab.
2. Click **Report a vulnerability**.
3. Provide a clear description, reproduction steps, affected versions, and
   any suggested mitigation.

The maintainer will try to acknowledge reports promptly and work with you to
confirm the issue, develop a fix, and coordinate disclosure. Because this is a
volunteer project, **no response or fix timelines are guaranteed**, and the
software is provided "as is" without warranty (see [NOTICE](NOTICE)).

This policy covers the `atonix` client library only. Vulnerabilities in the
Prometheus APM service itself should be reported to Prometheus Group.

If GitHub Private Vulnerability Reporting is not available to you, please
contact the maintainer listed in `pyproject.toml` directly.
