"""Opt-in black-box steering trajectory mode gate.

Keep package initialization lightweight so the default ``enabled=false`` path
does not import statistical, plotting, or provider libraries.
"""

from .config import ModeGateConfig

__all__ = ["ModeGateConfig"]
