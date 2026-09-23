# Copyright (c) 2026 MiniStack Contributors. SPDX-License-Identifier: MIT
# Copies or substantial portions, including AI-assisted ports or rewrites, must retain this notice (see LICENSE).
"""Lambda MicroVM collection operations."""

import asyncio
import json
from urllib.parse import quote

from ministack.core.responses import request_scope
from ministack.services import lambda_microvms


def _create_body(name):
    return json.dumps({
        "baseImageArn": "arn:aws:lambda:us-east-1:aws:microvm-image:base",
        "buildRoleArn": "arn:aws:iam::000000000000:role/build",
        "name": name,
        "codeArtifact": {"uri": "s3://bucket/artifact.zip"},
    }).encode()


def _request(method, path, body=b"", query_params=None):
    return asyncio.run(lambda_microvms.handle_request(
        method, path, {}, body, query_params or {}))


def test_list_microvm_images_returns_empty_collection():
    lambda_microvms.reset()
    try:
        with request_scope("000000000000", "us-east-1"):
            status, _, raw = _request("GET", "/2025-09-09/microvm-images")

        assert status == 200
        assert json.loads(raw) == {"items": []}
    finally:
        lambda_microvms.reset()


def test_list_microvm_images_filters_and_pages():
    lambda_microvms.reset()
    try:
        with request_scope("000000000000", "us-east-1"):
            for name in ("web", "worker", "worker-canary"):
                status, _, _ = _request(
                    "POST", "/2025-09-09/microvm-images", _create_body(name))
                assert status == 201

            status, _, raw = _request(
                "GET", "/2025-09-09/microvm-images",
                query_params={"nameFilter": ["worker"], "maxResults": ["1"]},
            )
            first_page = json.loads(raw)
            assert status == 200
            assert [item["name"] for item in first_page["items"]] == ["worker"]
            assert first_page["nextToken"] == "1"

            status, _, raw = _request(
                "GET", "/2025-09-09/microvm-images",
                query_params={
                    "nameFilter": ["worker"],
                    "maxResults": ["1"],
                    "nextToken": [first_page["nextToken"]],
                },
            )
            second_page = json.loads(raw)
            assert status == 200
            assert [item["name"] for item in second_page["items"]] == ["worker-canary"]
            assert "nextToken" not in second_page
    finally:
        lambda_microvms.reset()


def test_get_microvm_image_version_accepts_an_arn_path():
    lambda_microvms.reset()
    try:
        with request_scope("000000000000", "eu-west-1"):
            status, _, _ = _request(
                "POST", "/2025-09-09/microvm-images", _create_body("srea-gh-runner"))
            assert status == 201

            image_arn = (
                "arn:aws:lambda:eu-west-1:000000000000:"
                "microvm-image/srea-gh-runner"
            )
            status, _, raw = _request(
                "GET",
                f"/2025-09-09/microvm-images/{image_arn}/versions/1",
            )

        version = json.loads(raw)
        assert status == 200
        assert version["imageArn"] == image_arn
        assert version["imageVersion"] == "1"
        assert version["state"] == "SUCCESSFUL"
        assert version["status"] == "ACTIVE"
    finally:
        lambda_microvms.reset()


def test_get_and_update_microvm_image_support_the_publish_flow():
    lambda_microvms.reset()
    try:
        with request_scope("000000000000", "eu-west-1"):
            status, _, raw = _request(
                "POST", "/2025-09-09/microvm-images", _create_body("runner"))
            assert status == 201
            created = json.loads(raw)
            image_arn = created["imageArn"]

            status, _, raw = _request(
                "GET", f"/2025-09-09/microvm-images/{image_arn}")
            assert status == 200
            assert json.loads(raw)["state"] == "CREATED"

            status, _, raw = _request(
                "PUT",
                f"/2025-09-09/microvm-images/{image_arn}",
                _create_body("ignored-name"),
            )
            updated = json.loads(raw)
            assert status == 200
            assert updated["imageArn"] == image_arn
            assert updated["imageVersion"] == "2"
            assert updated["state"] == "UPDATED"

            status, _, raw = _request(
                "GET",
                f"/2025-09-09/microvm-images/{image_arn}/versions/2",
            )

        version = json.loads(raw)
        assert status == 200
        assert version["imageVersion"] == "2"
        assert version["state"] == "SUCCESSFUL"
        assert version["status"] == "ACTIVE"
    finally:
        lambda_microvms.reset()


def test_microvm_api_supports_packer_and_smoke_lifecycle():
    """Cover the image and MicroVM paths used by the local smoke workflow."""
    lambda_microvms.reset()
    try:
        with request_scope("000000000000", "eu-west-1"):
            run_hook_payload = "generic-microvm-payload"
            image_body = json.loads(_create_body("micro-ubuntu24"))
            image_body.update(
                {
                    "baseImageVersion": "al2023-1",
                    "cpuConfigurations": [{"architecture": "ARM_64"}],
                    "egressNetworkConnectors": [
                        "arn:aws:ec2:eu-west-1:000000000000:network-connector/ministack"
                    ],
                    "hooks": {
                        "port": 8080,
                        "microvmHooks": {
                            "run": "ENABLED",
                            "terminate": "ENABLED",
                        },
                        "microvmImageHooks": {
                            "ready": "ENABLED",
                            "validate": "ENABLED",
                        },
                    },
                    "logging": {
                        "cloudWatch": {
                            "logGroup": "/aws/lambda/microvms/ubuntu24",
                            "logStream": "micro-ubuntu24/ministack-smoke",
                        }
                    },
                    "resources": [{"minimumMemoryInMiB": 8192}],
                }
            )

            status, _, raw = _request(
                "POST",
                "/2025-09-09/microvm-images",
                json.dumps(image_body).encode(),
            )
            assert status == 201
            image = json.loads(raw)
            image_arn = image["imageArn"]
            assert image["state"] == "CREATED"

            encoded_image_arn = quote(image_arn, safe="")
            status, _, raw = _request(
                "GET",
                f"/2025-09-09/microvm-images/{encoded_image_arn}/versions/1",
            )
            version = json.loads(raw)
            assert status == 200
            assert version["imageArn"] == image_arn
            assert version["state"] == "SUCCESSFUL"
            assert version["status"] == "ACTIVE"
            assert version["hooks"] == image_body["hooks"]

            status, _, raw = _request(
                "POST",
                "/2025-09-09/microvms",
                json.dumps(
                    {
                        "imageIdentifier": image_arn,
                        "imageVersion": "1",
                        "runHookPayload": run_hook_payload,
                        "executionRoleArn": (
                            "arn:aws:iam::000000000000:role/microvm-runtime"
                        ),
                        "egressNetworkConnectors": image_body[
                            "egressNetworkConnectors"
                        ],
                    }
                ).encode(),
            )
            assert status == 200
            microvm = json.loads(raw)
            microvm_id = microvm["microvmId"]
            assert microvm["state"] == "RUNNING"
            assert microvm["imageArn"] == image_arn
            assert microvm["imageVersion"] == "1"
            assert (
                lambda_microvms.get_state()["microvms"][microvm_id][
                    "runHookPayload"
                ]
                == run_hook_payload
            )

            status, _, raw = _request(
                "GET", f"/2025-09-09/microvms/{microvm_id}"
            )
            assert status == 200
            assert json.loads(raw)["state"] == "RUNNING"

            status, _, _ = _request(
                "DELETE", f"/2025-09-09/microvms/{microvm_id}"
            )
            assert status == 200

            status, _, raw = _request(
                "GET", f"/2025-09-09/microvms/{microvm_id}"
            )
            terminated = json.loads(raw)
            assert status == 200
            assert terminated["state"] == "TERMINATED"
            assert "terminatedAt" in terminated
    finally:
        lambda_microvms.reset()
