"""Audit log: durable record of sensitive actions.

Use:
    from audit import log
    log("xero.connect", request=request, target=connection)

`log()` swallows its own exceptions so an audit failure can't break a
real flow. See `audit.helpers.log` for the implementation.
"""
from .helpers import log

__all__ = ["log"]
