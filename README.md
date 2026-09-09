# django-outbound-webhooks

[![CI](https://github.com/Artui/django-outbound-webhooks/workflows/tests/badge.svg)](https://github.com/Artui/django-outbound-webhooks/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/django-outbound-webhooks.svg)](https://pypi.org/project/django-outbound-webhooks/)
[![Python versions](https://img.shields.io/pypi/pyversions/django-outbound-webhooks.svg)](https://pypi.org/project/django-outbound-webhooks/)
[![Django versions](https://img.shields.io/pypi/djversions/django-outbound-webhooks.svg)](https://pypi.org/project/django-outbound-webhooks/)
[![Docs](https://img.shields.io/badge/docs-artui.github.io-blue.svg)](https://artui.github.io/django-outbound-webhooks/)
[![Coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Artui/django-outbound-webhooks/gh-pages/coverage.json)](https://github.com/Artui/django-outbound-webhooks/actions/workflows/tests.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/pypi/l/django-outbound-webhooks.svg)](LICENSE)

Outbound webhooks for Django, built on
[django-domain-events](https://github.com/Artui/django-domain-events).

Your customers subscribe to domain events, not to your `post_save` signals. An
endpoint is a row a customer owns: a URL, a secret, the events it wants and the
body format it was integrated against. Delivery is a durable receiver, so
retry, backoff, dead-lettering and replay are inherited rather than rebuilt.

## Install

```bash
pip install django-outbound-webhooks
```

## Status

Pre-release scaffold. The first release is 0.1.0.
