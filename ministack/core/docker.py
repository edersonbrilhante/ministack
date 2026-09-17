# Copyright (c) 2026 MiniStack Contributors. SPDX-License-Identifier: MIT
"""Shared capability gate for MiniStack's optional Docker data plane."""

import os


def docker_enabled() -> bool:
    """Whether production code may import or connect to Docker.

    Docker remains enabled by default for backwards compatibility.  Explicitly
    setting ``MINISTACK_DOCKER_ENABLED`` to a conventional false value disables
    every Docker access point, including cleanup and background reapers.
    """
    return os.environ.get("MINISTACK_DOCKER_ENABLED", "1").strip().lower() not in {
        "0", "false", "no", "off", "disabled",
    }
