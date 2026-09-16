"""An app the test settings do not install.

Installed partway through one test, after this package's delivery receiver has
been declared, so that an event comes into existence through Django's own app
loading and the substrate's own autodiscovery - later, and not by hand.
"""
