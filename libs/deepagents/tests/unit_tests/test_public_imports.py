"""Public imports keep backend-only consumers independent of agent startup."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap


def _run_in_fresh_process(source: str) -> None:
    environment = os.environ.copy()
    environment.update(LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false", PYTHONDONTWRITEBYTECODE="1")
    # Only test-owned Python source runs in the active package interpreter.
    subprocess.run([sys.executable, "-c", textwrap.dedent(source)], check=True, env=environment, timeout=30)  # noqa: S603


def test_backend_file_io_does_not_require_graph_or_provider_imports() -> None:
    _run_in_fresh_process("""
        import sys
        from importlib.abc import MetaPathFinder
        from pathlib import Path
        from tempfile import TemporaryDirectory

        class RefuseGraphAndProviders(MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                prefixes = ("deepagents.graph", "deepagents.middleware", "langchain_anthropic", "langchain_openai", "langchain_google_genai")
                if any(fullname == prefix or fullname.startswith(prefix + ".") for prefix in prefixes):
                    raise AssertionError("backend attempted unrelated import: " + fullname)
                return None

        sys.meta_path.insert(0, RefuseGraphAndProviders())
        from deepagents.backends import FilesystemBackend
        with TemporaryDirectory() as directory:
            backend = FilesystemBackend(root_dir=directory, virtual_mode=True)
            result = backend.write("/example.txt", "hello")
            assert result.error is None
            assert (Path(directory) / "example.txt").read_text() == "hello"
        assert "deepagents.graph" not in sys.modules
    """)


def test_public_names_are_discoverable_before_loading_the_graph() -> None:
    _run_in_fresh_process("""
        import sys
        import deepagents

        assert set(deepagents.__all__) <= set(dir(deepagents))
        assert isinstance(deepagents.__version__, str)
        assert "deepagents.graph" not in sys.modules
        try:
            deepagents.unknown_public_name
        except AttributeError as error:
            assert "unknown_public_name" in str(error)
        else:
            raise AssertionError("unknown attribute accepted")
        assert "deepagents.graph" not in sys.modules
    """)


def test_public_graph_exports_keep_original_types_and_run_a_turn() -> None:
    _run_in_fresh_process("""
        import deepagents
        from deepagents import DeepAgentState, FilesystemMiddleware, SubAgent, create_deep_agent
        from deepagents.graph import DeepAgentState as State, create_deep_agent as create
        from deepagents.middleware.filesystem import FilesystemMiddleware as Filesystem
        from deepagents.middleware.subagents import SubAgent as Agent
        from langchain_core.messages import AIMessage
        from tests.unit_tests.chat_model import GenericFakeChatModel

        assert DeepAgentState is State
        assert FilesystemMiddleware is Filesystem
        assert SubAgent is Agent
        assert create_deep_agent is create
        for name in deepagents.__all__:
            assert getattr(deepagents, name) is getattr(deepagents, name)
        model = GenericFakeChatModel(messages=iter([AIMessage(content="hello")]))
        agent = create_deep_agent(model=model)
        result = agent.invoke({"messages": [{"role": "user", "content": "ping"}]})
        assert result["messages"][-1].content == "hello"
        assert len(model.call_history) == 1
    """)


def test_concurrent_public_access_keeps_original_object_identity() -> None:
    _run_in_fresh_process("""
        from concurrent.futures import ThreadPoolExecutor
        import deepagents
        from deepagents.backends import FilesystemBackend

        names = [name for name in deepagents.__all__ if name != "__version__"] * 4
        with ThreadPoolExecutor(max_workers=8) as pool:
            values = list(pool.map(lambda name: getattr(deepagents, name), names))
        for name, value in zip(names, values, strict=True):
            assert value is getattr(deepagents, name), name
        assert FilesystemBackend is __import__("deepagents.backends", fromlist=["FilesystemBackend"]).FilesystemBackend
    """)


def test_profile_registration_survives_later_graph_import() -> None:
    _run_in_fresh_process("""
        from deepagents import ProviderProfile, register_provider_profile
        from deepagents.profiles.provider.provider_profiles import get_provider_profile

        register_provider_profile("owner2-fixture:local", ProviderProfile(init_kwargs={"timeout": 11}))
        import deepagents.graph
        profile = get_provider_profile("owner2-fixture:local")
        assert profile is not None
        assert profile.init_kwargs["timeout"] == 11
        register_provider_profile("owner2-fixture:local", ProviderProfile(init_kwargs={"max_retries": 2}))
        profile = get_provider_profile("owner2-fixture:local")
        assert profile.init_kwargs == {"timeout": 11, "max_retries": 2}
    """)
