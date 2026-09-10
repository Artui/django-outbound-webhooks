"""The customer-owned endpoint registry, and who an event is owed to.

Deliberately no re-exports. These are internal groupings, not public namespaces:
the package root is the public surface and re-exports everything, and every
module inside the package imports its neighbours by leaf path already.

Re-exporting here would buy nothing and cost a class of circular import, since a
leaf import runs the parent package first. django-domain-events learned that in
its own regroup, where an eager __init__ made a leaf import pull in a module that
imported back out. It also removes a carve-out this package used to need: with
nothing re-exported, no subpackage attribute can shadow the submodule whose
dotted path a migration froze.
"""
