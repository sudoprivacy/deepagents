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


def test_middleware_namespace_does_not_initialize_agent_components() -> None:
    _run_in_fresh_process("""
        import sys
        import deepagents.middleware as middleware

        assert set(middleware.__all__) <= set(dir(middleware))
        assert "deepagents.graph" not in sys.modules
        assert "deepagents.middleware.subagents" not in sys.modules
        assert "langchain_anthropic" not in sys.modules
        try:
            middleware.unknown_public_name
        except AttributeError as error:
            assert "deepagents.middleware" in str(error)
        else:
            raise AssertionError("unknown middleware accepted")
    """)


def test_subagent_reflection_does_not_load_unrelated_middleware() -> None:
    _run_in_fresh_process("""
        import sys
        from importlib.abc import MetaPathFinder
        from typing import get_type_hints

        class RefuseUnrelatedMiddleware(MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                unrelated = (
                    "deepagents.graph", "deepagents.middleware.async_subagents",
                    "deepagents.middleware.memory", "deepagents.middleware.rubric",
                    "deepagents.middleware.skills", "langchain_anthropic",
                    "langchain_openai", "langchain_google_genai",
                )
                if any(fullname == name or fullname.startswith(name + ".") for name in unrelated):
                    raise AssertionError("type reflection attempted unrelated import: " + fullname)
                return None

        sys.meta_path.insert(0, RefuseUnrelatedMiddleware())
        import deepagents
        from deepagents import SubAgent
        from deepagents.middleware import SubAgent as MiddlewareSubAgent
        from deepagents.middleware.subagents import SubAgent as OriginalSubAgent

        class Config:
            subagents: list[deepagents.SubAgent] | None

        assert SubAgent is MiddlewareSubAgent is OriginalSubAgent
        assert SubAgent.__module__ == "deepagents.middleware.subagents"
        assert get_type_hints(Config)["subagents"] == list[SubAgent] | None
        assert get_type_hints(SubAgent)["name"] is str
        assert set(SubAgent.__required_keys__) == {"name", "description"}
    """)


def test_concurrent_root_and_middleware_exports_share_original_definitions() -> None:
    _run_in_fresh_process("""
        from concurrent.futures import ThreadPoolExecutor
        import deepagents
        import deepagents.middleware as middleware

        requests = [(deepagents, name) for name in deepagents.__all__]
        requests += [(middleware, name) for name in middleware.__all__]
        requests *= 2
        with ThreadPoolExecutor(max_workers=8) as pool:
            values = list(pool.map(lambda item: getattr(*item), requests))
        for (module, name), value in zip(requests, values, strict=True):
            assert value is getattr(module, name)
            if name in middleware.__all__:
                assert value is getattr(middleware, name), name
    """)


def test_file_capabilities_preserve_actual_provider_classes_and_subclasses() -> None:
    _run_in_fresh_process("""
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_openai import AzureChatOpenAI, ChatOpenAI
        from deepagents.middleware.filesystem import _model_tolerates_non_pdf_files

        class CustomOpenAI(ChatOpenAI):
            pass

        for model_type in (ChatOpenAI, AzureChatOpenAI, ChatGoogleGenerativeAI, CustomOpenAI):
            assert _model_tolerates_non_pdf_files(model_type.model_construct())
        assert not _model_tolerates_non_pdf_files(None)
        assert not _model_tolerates_non_pdf_files(object())
    """)


def test_file_capabilities_work_when_optional_providers_are_unavailable() -> None:
    _run_in_fresh_process("""
        import sys
        from importlib.abc import MetaPathFinder

        class MissingProviders(MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname in ("langchain_openai", "langchain_google_genai"):
                    raise ModuleNotFoundError(fullname)
                return None

        sys.meta_path.insert(0, MissingProviders())
        from deepagents.middleware.filesystem import _model_tolerates_non_pdf_files
        assert not _model_tolerates_non_pdf_files(None)
        assert not _model_tolerates_non_pdf_files(object())
    """)
