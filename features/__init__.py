"""features — small wrapper around the FeatureFlag model.

Import surface kept minimal so callers stay terse::

    from features import is_enabled
    if is_enabled("ai_triage", user=request.user):
        ...
"""
from .helpers import is_enabled

default_app_config = "features.apps.FeaturesConfig"

__all__ = ["is_enabled"]
