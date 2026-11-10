from __future__ import annotations

from typing import Any

from django.contrib.auth import get_permission_codename
from django.http import HttpRequest


def may_change(request: HttpRequest, opts: Any) -> bool:
    """Whether this user holds one model's change permission."""
    user: Any = request.user
    return user.has_perm(f"{opts.app_label}.{get_permission_codename('change', opts)}")
