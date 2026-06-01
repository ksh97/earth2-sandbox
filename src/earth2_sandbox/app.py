"""Compatibility exports for FastAPI app construction.

New code should import from `earth2_sandbox.bootstrap.app_factory`.
"""

from earth2_sandbox.bootstrap.app_factory import create_app, create_app_from_container

__all__ = ["create_app", "create_app_from_container"]
