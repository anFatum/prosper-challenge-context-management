from __future__ import annotations


def __getattr__(name: str):
    if name in ("REGISTRY", "GLOBAL_TOOLS"):
        from .registry import GLOBAL_TOOLS, REGISTRY
        return {"REGISTRY": REGISTRY, "GLOBAL_TOOLS": GLOBAL_TOOLS}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["REGISTRY", "GLOBAL_TOOLS"]