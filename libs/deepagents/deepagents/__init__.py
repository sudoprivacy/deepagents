"""Deep Agents package."""

from importlib import import_module
from threading import RLock
from typing import TYPE_CHECKING

from deepagents._version import __version__

if TYPE_CHECKING:
    from deepagents.graph import DeepAgentState, create_deep_agent
    from deepagents.middleware.async_subagents import AsyncSubAgent, AsyncSubAgentMiddleware
    from deepagents.middleware.filesystem import FilesystemMiddleware, FilesystemPermission, FsToolName
    from deepagents.middleware.memory import MemoryMiddleware
    from deepagents.middleware.rubric import RubricMiddleware
    from deepagents.middleware.subagents import CompiledSubAgent, SubAgent, SubAgentMiddleware
    from deepagents.profiles.harness.harness_profiles import (
        GeneralPurposeSubagentProfile,
        HarnessProfile,
        HarnessProfileConfig,
        register_harness_profile,
    )
    from deepagents.profiles.provider.provider_profiles import ProviderProfile, register_provider_profile

# Importing a backend should not initialize the agent graph or provider SDKs.
# Keep the public API pointing at its original definitions when requested.
_EXPORTS: dict[str, str] = {
    "AsyncSubAgent": "deepagents.middleware.async_subagents",
    "AsyncSubAgentMiddleware": "deepagents.middleware.async_subagents",
    "CompiledSubAgent": "deepagents.middleware.subagents",
    "DeepAgentState": "deepagents.graph",
    "FilesystemMiddleware": "deepagents.middleware.filesystem",
    "FilesystemPermission": "deepagents.middleware.filesystem",
    "FsToolName": "deepagents.middleware.filesystem",
    "GeneralPurposeSubagentProfile": "deepagents.profiles.harness.harness_profiles",
    "HarnessProfile": "deepagents.profiles.harness.harness_profiles",
    "HarnessProfileConfig": "deepagents.profiles.harness.harness_profiles",
    "MemoryMiddleware": "deepagents.middleware.memory",
    "ProviderProfile": "deepagents.profiles.provider.provider_profiles",
    "RubricMiddleware": "deepagents.middleware.rubric",
    "SubAgent": "deepagents.middleware.subagents",
    "SubAgentMiddleware": "deepagents.middleware.subagents",
    "create_deep_agent": "deepagents.graph",
    "register_harness_profile": "deepagents.profiles.harness.harness_profiles",
    "register_provider_profile": "deepagents.profiles.provider.provider_profiles",
}

# Match eager package initialization's serialized first imports. The defining
# modules can request another public export while their own import is running.
_EXPORT_LOCK = RLock()


def __getattr__(name: str) -> object:
    """Resolve a public export without loading unrelated runtime components.

    Args:
        name: Public attribute requested by the caller.

    Returns:
        The object from its original defining module.

    Raises:
        AttributeError: If the requested name is not a public export.
    """
    return _resolve_export(name, globals(), _EXPORTS)


def _resolve_export(name: str, namespace: dict[str, object], exports: dict[str, str]) -> object:
    """Load package exports under one reentrant lock across public namespaces."""
    module = exports.get(name)
    if module is None:
        msg = f"module {namespace['__name__']!r} has no attribute {name!r}"
        raise AttributeError(msg)
    with _EXPORT_LOCK:
        value = getattr(import_module(module), name)
        namespace[name] = value
        return value


def __dir__() -> list[str]:
    """List public exports without importing their defining modules.

    Returns:
        The available module attribute names.
    """
    return sorted(set(globals()) | set(__all__))


__all__ = [
    "AsyncSubAgent",
    "AsyncSubAgentMiddleware",
    "CompiledSubAgent",
    "DeepAgentState",
    "FilesystemMiddleware",
    "FilesystemPermission",
    "FsToolName",
    "GeneralPurposeSubagentProfile",
    "HarnessProfile",
    "HarnessProfileConfig",
    "MemoryMiddleware",
    "ProviderProfile",
    "RubricMiddleware",
    "SubAgent",
    "SubAgentMiddleware",
    "__version__",
    "create_deep_agent",
    "register_harness_profile",
    "register_provider_profile",
]
