# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""Sync/async parity: every resource method must behave identically on both clients.

Each scenario below is run once through ``AtonixClient`` and once through
``AsyncAtonixClient`` against the same mocked API. The requests sent (method, URL
with query string, JSON body) and the outcome (result or raised exception) must match,
and must make the expected number of requests.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import respx
from httpx import Response

from atonix import (
    Assets,
    AsyncAssets,
    AsyncAtonixClient,
    AsyncIssues,
    AsyncModels,
    AsyncProcessData,
    AtonixClient,
    Issues,
    Models,
    ProcessData,
)
from atonix.object_models.issues import IssueCreate, IssueDiscussionEntryCreate, IssueKeyword, IssuePatch
from atonix.object_models.models import Model
from atonix.object_models.processdata import TagData
from tests.conftest import (
    BASE_URL,
    make_action_items,
    make_action_items_by_asset,
    make_alert_state,
    make_alert_states_by_asset,
    make_api_response,
    make_archives,
    make_asset,
    make_assets,
    make_bare_issues,
    make_discussion_entries,
    make_discussion_entry,
    make_external_model_config,
    make_issue,
    make_keyword,
    make_keywords,
    make_model_config,
    make_models,
    make_servers,
    make_tag,
    make_tags,
    query_echo_side_effect,
)

ASSET_ID = "00000000-0000-0000-0000-000000000001"
ISSUE_ID = "11111111-1111-1111-1111-111111111111"
MODEL_ID = "22222222-2222-2222-2222-222222222222"
SERVER_ID = "33333333-3333-3333-3333-333333333333"
TAG_ID = "44444444-4444-4444-4444-444444444444"
AFTER = datetime(2024, 1, 1, tzinfo=UTC)
BEFORE = datetime(2024, 2, 1, tzinfo=UTC)

RouteSpec = tuple[str, str, Any]  # (HTTP method, path, list of responses or a side-effect callable)


def ok(results: list[Any]) -> Response:
    return Response(200, json=make_api_response(results))


@dataclass
class Scenario:
    id: str
    resource: str
    method: str
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    routes: list[RouteSpec] = field(default_factory=list)
    requests: int = 1

    def mount(self, router: respx.MockRouter) -> None:
        for http_method, path, responses in self.routes:
            # Lists are copied so each run consumes its own sequence of responses.
            side_effect = list(responses) if isinstance(responses, list) else responses
            router.route(method=http_method, url=f"{BASE_URL}{path}").mock(side_effect=side_effect)


SCENARIOS = [
    # --- Assets ---
    Scenario(
        "assets.get_top paginates",
        "assets",
        "get_top",
        kwargs={"take": 2},
        routes=[("GET", "/v1/assets", [ok(make_assets(2)), ok(make_assets(1, start_index=2))])],
        requests=2,
    ),
    Scenario(
        "assets.get_asset_details",
        "assets",
        "get_asset_details",
        (ASSET_ID,),
        routes=[("GET", f"/v1/assets/{ASSET_ID}", [ok([make_asset()])])],
    ),
    Scenario(
        "assets.get_asset_details empty",
        "assets",
        "get_asset_details",
        (ASSET_ID,),
        routes=[("GET", f"/v1/assets/{ASSET_ID}", [ok([])])],
    ),
    Scenario(
        "assets.get_asset_details 404",
        "assets",
        "get_asset_details",
        (ASSET_ID,),
        routes=[("GET", f"/v1/assets/{ASSET_ID}", [Response(404, json={"Results": [{"Message": "nope"}]})])],
    ),
    Scenario(
        "assets.get_children filters",
        "assets",
        "get_children",
        (ASSET_ID,),
        {"include_descendants": True, "include_self": True, "changed_after": AFTER, "changed_before": BEFORE},
        routes=[("GET", f"/v1/assets/{ASSET_ID}/assets", [ok(make_assets(3))])],
    ),
    # --- Issues ---
    Scenario(
        "issues.get_issues filters",
        "issues",
        "get_issues",
        (ASSET_ID,),
        {"include_descendants": True, "status": "open", "changed_after": AFTER, "changed_before": BEFORE, "take": 2},
        routes=[("GET", "/v1/issues", [ok(make_bare_issues(2)), ok([])])],
        requests=2,
    ),
    Scenario(
        "issues.get_issue",
        "issues",
        "get_issue",
        (ISSUE_ID,),
        routes=[("GET", f"/v1/issues/{ISSUE_ID}", [ok([make_issue()])])],
    ),
    Scenario(
        "issues.create_issue",
        "issues",
        "create_issue",
        (IssueCreate(asset_id=ASSET_ID, title="T", category_desc="Maintenance", issue_class_type_desc="Mechanical"),),
        routes=[("POST", "/v1/issues", [ok([make_issue()])])],
    ),
    Scenario(
        "issues.create_issue empty",
        "issues",
        "create_issue",
        (IssueCreate(asset_id=ASSET_ID, title="T", category_desc="Maintenance", issue_class_type_desc="Mechanical"),),
        routes=[("POST", "/v1/issues", [ok([])])],
    ),
    Scenario(
        "issues.patch_issue",
        "issues",
        "patch_issue",
        (ISSUE_ID, IssuePatch(title="Patched", priority="High")),
        routes=[("PATCH", f"/v1/issues/{ISSUE_ID}", [ok([make_issue(title="Patched")])])],
    ),
    Scenario(
        "issues.patch_issue empty",
        "issues",
        "patch_issue",
        (ISSUE_ID, IssuePatch(title="Patched")),
        routes=[("PATCH", f"/v1/issues/{ISSUE_ID}", [ok([])])],
    ),
    Scenario(
        "issues.get_keywords",
        "issues",
        "get_keywords",
        (ISSUE_ID,),
        routes=[("GET", f"/v1/issues/{ISSUE_ID}/keywords", [ok(make_keywords(3))])],
    ),
    Scenario(
        "issues.add_keyword",
        "issues",
        "add_keyword",
        (ISSUE_ID, "pump"),
        routes=[("POST", f"/v1/issues/{ISSUE_ID}/keywords", [ok([make_keyword("pump")])])],
    ),
    Scenario(
        "issues.add_keyword empty",
        "issues",
        "add_keyword",
        (ISSUE_ID, "pump"),
        routes=[("POST", f"/v1/issues/{ISSUE_ID}/keywords", [ok([])])],
    ),
    Scenario(
        "issues.delete_keywords",
        "issues",
        "delete_keywords",
        (ISSUE_ID, ["pump", IssueKeyword(KeywordDesc="valve")]),
        routes=[("DELETE", f"/v1/issues/{ISSUE_ID}/keywords", [Response(200, json=make_api_response([]))])],
    ),
    Scenario("issues.delete_keywords none", "issues", "delete_keywords", (ISSUE_ID, []), requests=0),
    Scenario(
        "issues.create_discussion_entry",
        "issues",
        "create_discussion_entry",
        (ISSUE_ID, IssueDiscussionEntryCreate(title="T", contents="C")),
        routes=[("POST", f"/v1/issues/{ISSUE_ID}/discussionentries", [ok([make_discussion_entry()])])],
    ),
    Scenario(
        "issues.create_discussion_entry empty",
        "issues",
        "create_discussion_entry",
        (ISSUE_ID, IssueDiscussionEntryCreate(title="T", contents="C")),
        routes=[("POST", f"/v1/issues/{ISSUE_ID}/discussionentries", [ok([])])],
    ),
    Scenario(
        "issues.get_discussion_entries",
        "issues",
        "get_discussion_entries",
        (ISSUE_ID,),
        routes=[("GET", f"/v1/issues/{ISSUE_ID}/discussionentries", [ok(make_discussion_entries(2))])],
    ),
    Scenario(
        "issues.get_resolution_statuses",
        "issues",
        "get_resolution_statuses",
        (7,),
        routes=[("GET", "/v1/issues/resolutionstatuses", [ok([{"ResolutionStatus": "Monitoring"}])])],
    ),
    # --- Models ---
    Scenario(
        "models.get_models",
        "models",
        "get_models",
        (ASSET_ID,),
        {"include_descendants": True},
        routes=[("GET", "/v1/models", [ok(make_models(3))])],
    ),
    Scenario(
        "models.get_model_state",
        "models",
        "get_model_state",
        (MODEL_ID,),
        routes=[("GET", f"/v1/models/{MODEL_ID}/state", [ok([make_alert_state()])])],
    ),
    Scenario(
        "models.get_model_actions filters",
        "models",
        "get_model_actions",
        (MODEL_ID,),
        {"changed_after": AFTER, "changed_before": BEFORE},
        routes=[("GET", f"/v1/models/{MODEL_ID}/actions", [ok(make_action_items(2))])],
    ),
    Scenario(
        "models.get_model_config standard",
        "models",
        "get_model_config",
        (MODEL_ID,),
        routes=[("GET", f"/v1/models/{MODEL_ID}/config", [ok([make_model_config()])])],
    ),
    Scenario(
        "models.get_model_config external",
        "models",
        "get_model_config",
        (MODEL_ID,),
        routes=[
            (
                "GET",
                f"/v1/models/{MODEL_ID}/config",
                [
                    Response(
                        200,
                        json=make_api_response([make_external_model_config()], type_name="ExternalModelConfiguration"),
                    )
                ],
            )
        ],
    ),
    Scenario(
        "models.get_model_states_by_asset",
        "models",
        "get_model_states_by_asset",
        (ASSET_ID,),
        {"include_descendants": True, "include_inactive": True},
        routes=[("GET", "/v1/models/state", [ok(make_alert_states_by_asset(2))])],
    ),
    Scenario(
        "models.get_model_actions_by_asset flags",
        "models",
        "get_model_actions_by_asset",
        (ASSET_ID, AFTER, BEFORE),
        {"favorite": True, "include_descendants": True},
        routes=[("GET", "/v1/models/actions", [ok(make_action_items_by_asset(2))])],
    ),
    Scenario(
        "models.get_model everything",
        "models",
        "get_model",
        (Model(Id=MODEL_ID, Name="Existing"),),
        {"include_config": True, "include_state": True, "include_actions": True, "actions_changed_after": AFTER},
        routes=[
            ("GET", f"/v1/models/{MODEL_ID}/config", [ok([make_model_config()])]),
            ("GET", f"/v1/models/{MODEL_ID}/state", [ok([make_alert_state()])]),
            ("GET", f"/v1/models/{MODEL_ID}/actions", [ok(make_action_items(2))]),
        ],
        requests=3,
    ),
    Scenario(
        "models.get_model partial failure",
        "models",
        "get_model",
        (MODEL_ID,),
        {"include_config": True, "include_state": True, "include_actions": True},
        routes=[
            ("GET", f"/v1/models/{MODEL_ID}/config", [Response(404, json={"Results": [{"Message": "nope"}]})]),
            ("GET", f"/v1/models/{MODEL_ID}/state", [ok([])]),
            ("GET", f"/v1/models/{MODEL_ID}/actions", [ok(make_action_items(1))]),
        ],
        requests=3,
    ),
    # --- ProcessData ---
    Scenario(
        "process_data.get_servers",
        "process_data",
        "get_servers",
        kwargs={"take": 2},
        routes=[("GET", "/v1/processdata/servers", [ok(make_servers(2)), ok(make_servers(1, start_index=2))])],
        requests=2,
    ),
    Scenario(
        "process_data.get_tags_list filters",
        "process_data",
        "get_tags_list",
        (SERVER_ID,),
        {"changed_after": AFTER, "changed_before": BEFORE},
        routes=[("GET", f"/v1/processdata/servers/{SERVER_ID}/tags", [ok(make_tags(2))])],
    ),
    Scenario(
        "process_data.get_tag_details",
        "process_data",
        "get_tag_details",
        (TAG_ID,),
        routes=[("GET", f"/v1/processdata/tags/{TAG_ID}", [ok([make_tag()])])],
    ),
    Scenario(
        "process_data.get_archives",
        "process_data",
        "get_archives",
        (SERVER_ID,),
        routes=[("GET", f"/v1/processdata/servers/{SERVER_ID}/archives", [ok(make_archives(4))])],
    ),
    Scenario(
        "process_data.get_data_for_range",
        "process_data",
        "get_data_for_range",
        (SERVER_ID, AFTER, AFTER + timedelta(hours=1), [TAG_ID], "1min"),
        routes=[
            ("GET", f"/v1/processdata/servers/{SERVER_ID}/archives", [ok(make_archives(4))]),
            ("POST", "/v1/processdata/query", query_echo_side_effect),
        ],
        requests=2,
    ),
    Scenario(
        "process_data.get_data_for_range chunked",
        "process_data",
        "get_data_for_range",
        (SERVER_ID, AFTER, AFTER + timedelta(days=200), [TAG_ID, "tag-2"], "1min"),
        routes=[
            ("GET", f"/v1/processdata/servers/{SERVER_ID}/archives", [ok(make_archives(4))]),
            ("POST", "/v1/processdata/query", query_echo_side_effect),
        ],
        requests=4,  # 1 archive lookup + 3 time-window sub-queries
    ),
    Scenario(
        "process_data.get_data_for_range too large",
        "process_data",
        "get_data_for_range",
        (SERVER_ID, AFTER, AFTER + timedelta(days=200), [TAG_ID], "1min"),
        {"chunk": False},
        routes=[("GET", f"/v1/processdata/servers/{SERVER_ID}/archives", [ok(make_archives(4))])],
    ),
    Scenario(
        "process_data.get_data_for_range unknown archive",
        "process_data",
        "get_data_for_range",
        (SERVER_ID, AFTER, BEFORE, [TAG_ID], "7min"),
        routes=[("GET", f"/v1/processdata/servers/{SERVER_ID}/archives", [ok(make_archives(4))])],
    ),
    Scenario(
        "process_data.get_data_for_range bad range",
        "process_data",
        "get_data_for_range",
        (SERVER_ID, BEFORE, AFTER, [TAG_ID], "1min"),
        requests=0,
    ),
    Scenario(
        "process_data.write_tag_data batches",
        "process_data",
        "write_tag_data",
        (
            SERVER_ID,
            "1min",
            [
                TagData(
                    TagId=f"tag-{n}",
                    Data={
                        "Timestamps": [(AFTER + timedelta(minutes=i)).isoformat() for i in range(20_000)],
                        "Values": [float(i) for i in range(20_000)],
                    },
                )
                for n in range(2)
            ],
        ),
        routes=[("POST", "/v1/processdata/write", lambda request: Response(200, json=make_api_response([])))],
        requests=2,
    ),
]


@dataclass
class Outcome:
    result: Any = None
    error: tuple[type[BaseException], str] | None = None
    requests: list[tuple[str, str, Any]] = field(default_factory=list)


def _recorded(router: respx.MockRouter) -> list[tuple[str, str, Any]]:
    return [
        (call.request.method, str(call.request.url), json.loads(call.request.content) if call.request.content else None)
        for call in router.calls
    ]


def _run_sync(client: AtonixClient, scenario: Scenario) -> Outcome:
    outcome = Outcome()
    with respx.mock(assert_all_called=False) as router:
        scenario.mount(router)
        try:
            result = getattr(getattr(client, scenario.resource), scenario.method)(*scenario.args, **scenario.kwargs)
            outcome.result = list(result) if isinstance(result, Iterator) else result
        except Exception as e:
            outcome.error = (type(e), str(e))
        outcome.requests = _recorded(router)
    return outcome


async def _run_async(client: AsyncAtonixClient, scenario: Scenario) -> Outcome:
    outcome = Outcome()
    with respx.mock(assert_all_called=False) as router:
        scenario.mount(router)
        try:
            result = getattr(getattr(client, scenario.resource), scenario.method)(*scenario.args, **scenario.kwargs)
            if isinstance(result, AsyncIterator):
                outcome.result = [item async for item in result]
            else:
                outcome.result = await result
        except Exception as e:
            outcome.error = (type(e), str(e))
        outcome.requests = _recorded(router)
    return outcome


@pytest.mark.anyio
@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.id)
async def test_sync_and_async_behave_identically(scenario: Scenario, mock_private_key) -> None:
    sync_client = AtonixClient(api_key="testkey", private_key=mock_private_key, max_retries=0)
    async_client = AsyncAtonixClient(api_key="testkey", private_key=mock_private_key, max_retries=0)
    try:
        sync_outcome = _run_sync(sync_client, scenario)
        async_outcome = await _run_async(async_client, scenario)
    finally:
        sync_client.close()
        await async_client.aclose()

    assert len(sync_outcome.requests) == scenario.requests
    assert sync_outcome.requests == async_outcome.requests
    assert sync_outcome.error == async_outcome.error
    assert sync_outcome.result == async_outcome.result


def test_paginated_methods_are_lazy(mock_client) -> None:
    """Calling a paginated method sends nothing until iteration starts, on both paths."""
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{BASE_URL}/v1/assets").mock(return_value=ok([]))
        iterator = mock_client.assets.get_top()
        assert not router.calls
        assert list(iterator) == []
        assert len(router.calls) == 1


# --- Structural parity: the two public surfaces must not drift apart ---

PAIRS: list[tuple[type, type]] = [
    (Assets, AsyncAssets),
    (Issues, AsyncIssues),
    (Models, AsyncModels),
    (ProcessData, AsyncProcessData),
]


def _public_methods(cls: type) -> dict[str, Callable[..., Any]]:
    return {name: fn for name, fn in inspect.getmembers(cls, inspect.isfunction) if not name.startswith("_")}


@pytest.mark.parametrize(("sync_cls", "async_cls"), PAIRS, ids=lambda c: c.__name__)
def test_public_surfaces_match(sync_cls: type, async_cls: type) -> None:
    sync_methods = _public_methods(sync_cls)
    async_methods = _public_methods(async_cls)
    assert sync_methods.keys() == async_methods.keys()

    for name, sync_fn in sync_methods.items():
        async_fn = async_methods[name]
        sync_sig, async_sig = inspect.signature(sync_fn), inspect.signature(async_fn)
        assert list(sync_sig.parameters.values()) == list(async_sig.parameters.values()), name
        assert sync_fn.__doc__ and async_fn.__doc__, f"{name} must be documented on both classes"
        assert not inspect.iscoroutinefunction(sync_fn), name

        sync_ret, async_ret = str(sync_sig.return_annotation), str(async_sig.return_annotation)
        if sync_ret.startswith("Iterator["):
            # Paginated: a plain method returning an async iterator of the same item type.
            assert async_ret == f"Async{sync_ret}", name
            assert not inspect.iscoroutinefunction(async_fn), name
        else:
            assert async_ret == sync_ret, name
            assert inspect.iscoroutinefunction(async_fn), name
