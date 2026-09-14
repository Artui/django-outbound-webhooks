"""Helpers shared by this package's ModelAdmins, exported from nowhere."""

from __future__ import annotations

from typing import Any

from django.contrib.auth import get_permission_codename
from django.http import HttpRequest


def may_change(request: HttpRequest, opts: Any) -> bool:
    """Whether this user holds one model's change permission.

    Every action here gates on this, because Django's default is the wrong way
    round: an action declared without ``permissions=`` is offered to **anyone
    who can reach the changelist**, which includes view-only staff, and
    ``has_change_permission`` gates the form rather than the action, so refusing
    there refuses nothing. The failure is silent in the worst way -- the action
    runs, and the only sign is a delivery the operator did not expect to be able
    to send.

    A model's change permission rather than a custom one: it already means "may
    mutate these rows", which needs no migration and no new vocabulary for an
    operator to learn. ``get_permission_codename`` rather than an f-string, so a
    model that renames its permissions is still asked about the right one.

    ``opts`` is passed in rather than read off the admin, because the permission
    that governs an action is not always the one for the table it is listed
    under -- see the replay action, which is listed on the log and lands on an
    endpoint.

    ``request.user`` is typed as possibly anonymous and ``has_perm`` lives on
    ``PermissionsMixin``, which a swapped user model need not have. Django's own
    ``ModelAdmin`` calls it unconditionally here; the ``Any`` records that this
    is that boundary.
    """
    user: Any = request.user
    return user.has_perm(f"{opts.app_label}.{get_permission_codename('change', opts)}")
