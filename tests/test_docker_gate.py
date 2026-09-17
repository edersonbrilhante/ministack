"""The product Docker capability gate is hard, including cleanup paths."""

import importlib

import pytest


@pytest.mark.parametrize(
    "module_name, getter",
    [
        ("ecs", "_get_docker"),
        ("codebuild", "_get_docker"),
        ("ec2", "_get_docker"),
        ("eks", "_get_docker"),
        ("elasticache", "_get_docker"),
        ("glue", "_get_docker"),
        ("mwaa", "_get_docker"),
        ("opensearch", "_get_docker"),
        ("rds", "_get_docker"),
        ("lambda_svc", "_get_docker_client"),
    ],
)
def test_disabled_gate_prevents_docker_client_creation(monkeypatch, module_name, getter):
    monkeypatch.setenv("MINISTACK_DOCKER_ENABLED", "0")
    module = importlib.import_module(f"ministack.services.{module_name}")
    assert getattr(module, getter)() is None


def test_disabled_gate_skips_app_reaper_client(monkeypatch):
    monkeypatch.setenv("MINISTACK_DOCKER_ENABLED", "false")
    app = importlib.import_module("ministack.app")
    assert app._reaper_docker_client() is None


def test_disabled_gate_skips_dsql_docker_preflight(monkeypatch):
    monkeypatch.setenv("MINISTACK_DOCKER_ENABLED", "0")
    dsql = importlib.import_module("ministack.services.dsql")
    assert dsql._docker_available() is False


def test_gate_defaults_to_enabled(monkeypatch):
    monkeypatch.delenv("MINISTACK_DOCKER_ENABLED", raising=False)
    from ministack.core.docker import docker_enabled

    assert docker_enabled()
