# django-outbound-webhooks

Outbound webhooks for Django: a customer-facing endpoint registry, Standard
Webhooks signing, and per-endpoint delivery built as a durable receiver on
[django-domain-events](https://github.com/Artui/django-domain-events).

Your customers subscribe to domain events, not to your `post_save` signals.
