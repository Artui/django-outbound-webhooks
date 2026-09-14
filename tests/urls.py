"""URLs for the test suite: the admin, and nothing else.

Mounted so the admin pages can be driven with the test client rather than by
instantiating a ModelAdmin and calling its methods. The difference matters here:
the action-permission hazard this package guards against lives in how Django
*offers* an action on the changelist, which a direct call cannot reach.
"""

from __future__ import annotations

from django.contrib import admin
from django.urls import URLPattern, URLResolver, path

urlpatterns: list[URLPattern | URLResolver] = [path("admin/", admin.site.urls)]
