import datetime

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


def _future_date(days: int = 7) -> str:
    return (datetime.date.today() + datetime.timedelta(days=days)).isoformat()


def _past_date(days: int = 1) -> str:
    return (datetime.date.today() - datetime.timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# POST /tasks — Creation
# ---------------------------------------------------------------------------

class TestCreateTask:
    async def test_create_task_success(self, client: AsyncClient):
        payload = {
            "title": "Write tests",
            "priority": 3,
            "due_date": _future_date(),
            "tags": ["work", "urgent"],
        }
        resp = await client.post("/tasks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Write tests"
        assert data["priority"] == 3
        assert data["completed"] is False
        assert len(data["tags"]) == 2
        tag_names = {t["name"] for t in data["tags"]}
        assert tag_names == {"work", "urgent"}

    async def test_create_task_with_description(self, client: AsyncClient):
        payload = {
            "title": "Task with desc",
            "description": "Some details here",
            "priority": 1,
            "due_date": _future_date(),
        }
        resp = await client.post("/tasks", json=payload)
        assert resp.status_code == 201
        assert resp.json()["description"] == "Some details here"

    async def test_create_task_no_tags(self, client: AsyncClient):
        payload = {"title": "No tags", "priority": 2, "due_date": _future_date()}
        resp = await client.post("/tasks", json=payload)
        assert resp.status_code == 201
        assert resp.json()["tags"] == []

    async def test_create_task_missing_title(self, client: AsyncClient):
        payload = {"priority": 3, "due_date": _future_date()}
        resp = await client.post("/tasks", json=payload)
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"] == "Validation Failed"
        assert "title" in body["details"]

    async def test_create_task_empty_title(self, client: AsyncClient):
        payload = {"title": "", "priority": 3, "due_date": _future_date()}
        resp = await client.post("/tasks", json=payload)
        assert resp.status_code == 422

    async def test_create_task_title_too_long(self, client: AsyncClient):
        payload = {"title": "x" * 201, "priority": 3, "due_date": _future_date()}
        resp = await client.post("/tasks", json=payload)
        assert resp.status_code == 422

    async def test_create_task_priority_too_low(self, client: AsyncClient):
        payload = {"title": "Bad priority", "priority": 0, "due_date": _future_date()}
        resp = await client.post("/tasks", json=payload)
        assert resp.status_code == 422
        assert "priority" in resp.json()["details"]

    async def test_create_task_priority_too_high(self, client: AsyncClient):
        payload = {"title": "Bad priority", "priority": 6, "due_date": _future_date()}
        resp = await client.post("/tasks", json=payload)
        assert resp.status_code == 422

    async def test_create_task_past_due_date(self, client: AsyncClient):
        payload = {"title": "Past date", "priority": 1, "due_date": _past_date()}
        resp = await client.post("/tasks", json=payload)
        assert resp.status_code == 422
        assert "due_date" in resp.json()["details"]

    async def test_create_task_invalid_date_format(self, client: AsyncClient):
        payload = {"title": "Bad date", "priority": 1, "due_date": "13-01-2030"}
        resp = await client.post("/tasks", json=payload)
        assert resp.status_code == 422

    async def test_create_task_missing_priority(self, client: AsyncClient):
        payload = {"title": "No priority", "due_date": _future_date()}
        resp = await client.post("/tasks", json=payload)
        assert resp.status_code == 422
        assert "priority" in resp.json()["details"]

    async def test_create_task_missing_due_date(self, client: AsyncClient):
        payload = {"title": "No date", "priority": 3}
        resp = await client.post("/tasks", json=payload)
        assert resp.status_code == 422
        assert "due_date" in resp.json()["details"]

    async def test_create_task_tags_normalised_to_lowercase(self, client: AsyncClient):
        payload = {"title": "Tag case", "priority": 2, "due_date": _future_date(), "tags": ["WORK", "  Urgent  "]}
        resp = await client.post("/tasks", json=payload)
        assert resp.status_code == 201
        tag_names = {t["name"] for t in resp.json()["tags"]}
        assert tag_names == {"work", "urgent"}

    async def test_create_task_duplicate_tags_handled(self, client: AsyncClient):
        payload = {"title": "Dup tags", "priority": 1, "due_date": _future_date(), "tags": ["work", "work"]}
        resp = await client.post("/tasks", json=payload)
        assert resp.status_code == 201

    async def test_create_task_empty_tags_list(self, client: AsyncClient):
        payload = {"title": "Empty tags", "priority": 1, "due_date": _future_date(), "tags": []}
        resp = await client.post("/tasks", json=payload)
        assert resp.status_code == 201
        assert resp.json()["tags"] == []

    async def test_create_task_today_due_date_accepted(self, client: AsyncClient):
        today = datetime.date.today().isoformat()
        payload = {"title": "Due today", "priority": 1, "due_date": today}
        resp = await client.post("/tasks", json=payload)
        assert resp.status_code == 201
        assert resp.json()["due_date"] == today

    async def test_create_task_priority_boundary_1(self, client: AsyncClient):
        payload = {"title": "P1", "priority": 1, "due_date": _future_date()}
        resp = await client.post("/tasks", json=payload)
        assert resp.status_code == 201
        assert resp.json()["priority"] == 1

    async def test_create_task_priority_boundary_5(self, client: AsyncClient):
        payload = {"title": "P5", "priority": 5, "due_date": _future_date()}
        resp = await client.post("/tasks", json=payload)
        assert resp.status_code == 201
        assert resp.json()["priority"] == 5

    async def test_create_task_response_has_timestamps(self, client: AsyncClient):
        payload = {"title": "Timestamps", "priority": 2, "due_date": _future_date()}
        resp = await client.post("/tasks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert "created_at" in data
        assert "updated_at" in data
        assert data["is_deleted"] is False


# ---------------------------------------------------------------------------
# GET /tasks — Listing, Filtering, Pagination
# ---------------------------------------------------------------------------

class TestListTasks:
    async def _seed_tasks(self, client: AsyncClient):
        """Create a known set of tasks for filter tests."""
        tasks = [
            {"title": "Task A", "priority": 5, "due_date": _future_date(), "tags": ["work"]},
            {"title": "Task B", "priority": 3, "due_date": _future_date(), "tags": ["personal"]},
            {"title": "Task C", "priority": 1, "due_date": _future_date(), "tags": ["work", "urgent"]},
            {"title": "Task D", "priority": 5, "due_date": _future_date(), "tags": ["urgent"]},
        ]
        ids = []
        for t in tasks:
            resp = await client.post("/tasks", json=t)
            assert resp.status_code == 201
            ids.append(resp.json()["id"])
        return ids

    async def test_list_all(self, client: AsyncClient):
        await self._seed_tasks(client)
        resp = await client.get("/tasks")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 4
        assert "tasks" in body
        assert "limit" in body
        assert "offset" in body

    async def test_filter_by_priority(self, client: AsyncClient):
        await self._seed_tasks(client)
        resp = await client.get("/tasks", params={"priority": 5})
        assert resp.status_code == 200
        for task in resp.json()["tasks"]:
            assert task["priority"] == 5

    async def test_filter_by_completed(self, client: AsyncClient):
        ids = await self._seed_tasks(client)
        # Mark one task completed
        await client.patch(f"/tasks/{ids[0]}", json={"completed": True})
        resp = await client.get("/tasks", params={"completed": True})
        assert resp.status_code == 200
        for task in resp.json()["tasks"]:
            assert task["completed"] is True

    async def test_filter_by_tags(self, client: AsyncClient):
        await self._seed_tasks(client)
        resp = await client.get("/tasks", params={"tags": "urgent"})
        assert resp.status_code == 200
        for task in resp.json()["tasks"]:
            tag_names = {t["name"] for t in task["tags"]}
            assert "urgent" in tag_names

    async def test_filter_by_multiple_tags(self, client: AsyncClient):
        await self._seed_tasks(client)
        resp = await client.get("/tasks", params={"tags": "work,personal"})
        assert resp.status_code == 200
        for task in resp.json()["tasks"]:
            tag_names = {t["name"] for t in task["tags"]}
            assert tag_names & {"work", "personal"}

    async def test_pagination_limit_offset(self, client: AsyncClient):
        await self._seed_tasks(client)
        resp = await client.get("/tasks", params={"limit": 2, "offset": 0})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["tasks"]) <= 2
        assert body["limit"] == 2
        assert body["offset"] == 0

    async def test_pagination_offset(self, client: AsyncClient):
        await self._seed_tasks(client)
        resp_page1 = await client.get("/tasks", params={"limit": 2, "offset": 0})
        resp_page2 = await client.get("/tasks", params={"limit": 2, "offset": 2})
        ids_page1 = {t["id"] for t in resp_page1.json()["tasks"]}
        ids_page2 = {t["id"] for t in resp_page2.json()["tasks"]}
        assert ids_page1.isdisjoint(ids_page2)

    async def test_filter_priority_and_tags_combined(self, client: AsyncClient):
        await self._seed_tasks(client)
        resp = await client.get("/tasks", params={"priority": 5, "tags": "urgent"})
        assert resp.status_code == 200
        for task in resp.json()["tasks"]:
            assert task["priority"] == 5
            tag_names = {t["name"] for t in task["tags"]}
            assert "urgent" in tag_names

    async def test_filter_completed_false(self, client: AsyncClient):
        await self._seed_tasks(client)
        resp = await client.get("/tasks", params={"completed": False})
        assert resp.status_code == 200
        for task in resp.json()["tasks"]:
            assert task["completed"] is False

    async def test_filter_nonexistent_tag_returns_empty(self, client: AsyncClient):
        await self._seed_tasks(client)
        resp = await client.get("/tasks", params={"tags": "nonexistent_xyz"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["tasks"] == []

    async def test_deleted_tasks_excluded_from_listing(self, client: AsyncClient):
        ids = await self._seed_tasks(client)
        await client.delete(f"/tasks/{ids[0]}")
        resp = await client.get("/tasks")
        listed_ids = {t["id"] for t in resp.json()["tasks"]}
        assert ids[0] not in listed_ids

    async def test_offset_beyond_total_returns_empty(self, client: AsyncClient):
        await self._seed_tasks(client)
        resp = await client.get("/tasks", params={"offset": 9999})
        assert resp.status_code == 200
        assert resp.json()["tasks"] == []
        assert resp.json()["total"] >= 4

    async def test_list_empty_database(self, client: AsyncClient):
        resp = await client.get("/tasks")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["tasks"] == []


# ---------------------------------------------------------------------------
# GET /tasks/{id}
# ---------------------------------------------------------------------------

class TestGetTask:
    async def test_get_existing_task(self, client: AsyncClient):
        create_resp = await client.post(
            "/tasks", json={"title": "Fetch me", "priority": 2, "due_date": _future_date()}
        )
        task_id = create_resp.json()["id"]
        resp = await client.get(f"/tasks/{task_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Fetch me"

    async def test_get_nonexistent_task(self, client: AsyncClient):
        resp = await client.get("/tasks/99999")
        assert resp.status_code == 404
        assert resp.json()["error"] == "Task not found"


# ---------------------------------------------------------------------------
# PATCH /tasks/{id} — Partial Updates
# ---------------------------------------------------------------------------

class TestUpdateTask:
    async def _create_task(self, client: AsyncClient) -> int:
        resp = await client.post(
            "/tasks",
            json={"title": "Updatable", "priority": 2, "due_date": _future_date(), "tags": ["original"]},
        )
        return resp.json()["id"]

    async def test_update_title_only(self, client: AsyncClient):
        task_id = await self._create_task(client)
        resp = await client.patch(f"/tasks/{task_id}", json={"title": "Updated Title"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Title"
        assert data["priority"] == 2  # unchanged

    async def test_update_priority(self, client: AsyncClient):
        task_id = await self._create_task(client)
        resp = await client.patch(f"/tasks/{task_id}", json={"priority": 5})
        assert resp.status_code == 200
        assert resp.json()["priority"] == 5

    async def test_update_completed(self, client: AsyncClient):
        task_id = await self._create_task(client)
        resp = await client.patch(f"/tasks/{task_id}", json={"completed": True})
        assert resp.status_code == 200
        assert resp.json()["completed"] is True

    async def test_update_tags(self, client: AsyncClient):
        task_id = await self._create_task(client)
        resp = await client.patch(f"/tasks/{task_id}", json={"tags": ["new-tag", "another"]})
        assert resp.status_code == 200
        tag_names = {t["name"] for t in resp.json()["tags"]}
        assert tag_names == {"new-tag", "another"}

    async def test_update_clear_tags(self, client: AsyncClient):
        task_id = await self._create_task(client)
        resp = await client.patch(f"/tasks/{task_id}", json={"tags": []})
        assert resp.status_code == 200
        assert resp.json()["tags"] == []

    async def test_update_due_date(self, client: AsyncClient):
        task_id = await self._create_task(client)
        new_date = _future_date(30)
        resp = await client.patch(f"/tasks/{task_id}", json={"due_date": new_date})
        assert resp.status_code == 200
        assert resp.json()["due_date"] == new_date

    async def test_update_invalid_priority(self, client: AsyncClient):
        task_id = await self._create_task(client)
        resp = await client.patch(f"/tasks/{task_id}", json={"priority": 10})
        assert resp.status_code == 422

    async def test_update_past_due_date(self, client: AsyncClient):
        task_id = await self._create_task(client)
        resp = await client.patch(f"/tasks/{task_id}", json={"due_date": _past_date()})
        assert resp.status_code == 422

    async def test_update_nonexistent_task(self, client: AsyncClient):
        resp = await client.patch("/tasks/99999", json={"title": "Nope"})
        assert resp.status_code == 404

    async def test_update_empty_body_no_change(self, client: AsyncClient):
        task_id = await self._create_task(client)
        resp = await client.patch(f"/tasks/{task_id}", json={})
        assert resp.status_code == 200

    async def test_update_description(self, client: AsyncClient):
        task_id = await self._create_task(client)
        resp = await client.patch(f"/tasks/{task_id}", json={"description": "New description"})
        assert resp.status_code == 200
        assert resp.json()["description"] == "New description"

    async def test_update_multiple_fields_at_once(self, client: AsyncClient):
        task_id = await self._create_task(client)
        new_date = _future_date(60)
        resp = await client.patch(
            f"/tasks/{task_id}",
            json={"title": "Multi update", "priority": 4, "due_date": new_date, "completed": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Multi update"
        assert data["priority"] == 4
        assert data["due_date"] == new_date
        assert data["completed"] is True
        # tags should still be the original
        assert len(data["tags"]) == 1
        assert data["tags"][0]["name"] == "original"

    async def test_update_preserves_unset_fields(self, client: AsyncClient):
        task_id = await self._create_task(client)
        original = (await client.get(f"/tasks/{task_id}")).json()
        await client.patch(f"/tasks/{task_id}", json={"title": "Changed"})
        updated = (await client.get(f"/tasks/{task_id}")).json()
        assert updated["title"] == "Changed"
        assert updated["priority"] == original["priority"]
        assert updated["due_date"] == original["due_date"]
        assert updated["description"] == original["description"]

    async def test_update_title_too_long(self, client: AsyncClient):
        task_id = await self._create_task(client)
        resp = await client.patch(f"/tasks/{task_id}", json={"title": "x" * 201})
        assert resp.status_code == 422

    async def test_update_title_empty_string(self, client: AsyncClient):
        task_id = await self._create_task(client)
        resp = await client.patch(f"/tasks/{task_id}", json={"title": ""})
        assert resp.status_code == 422

    async def test_update_invalid_date_format(self, client: AsyncClient):
        task_id = await self._create_task(client)
        resp = await client.patch(f"/tasks/{task_id}", json={"due_date": "not-a-date"})
        assert resp.status_code == 422

    async def test_update_deleted_task_returns_404(self, client: AsyncClient):
        task_id = await self._create_task(client)
        await client.delete(f"/tasks/{task_id}")
        resp = await client.patch(f"/tasks/{task_id}", json={"title": "Nope"})
        assert resp.status_code == 404

    async def test_update_tags_with_new_and_existing(self, client: AsyncClient):
        task_id = await self._create_task(client)
        resp = await client.patch(f"/tasks/{task_id}", json={"tags": ["original", "brand-new"]})
        assert resp.status_code == 200
        tag_names = {t["name"] for t in resp.json()["tags"]}
        assert tag_names == {"original", "brand-new"}

    async def test_toggle_completed_back_and_forth(self, client: AsyncClient):
        task_id = await self._create_task(client)
        resp1 = await client.patch(f"/tasks/{task_id}", json={"completed": True})
        assert resp1.json()["completed"] is True
        resp2 = await client.patch(f"/tasks/{task_id}", json={"completed": False})
        assert resp2.json()["completed"] is False


# ---------------------------------------------------------------------------
# DELETE /tasks/{id} — Soft Delete
# ---------------------------------------------------------------------------

class TestDeleteTask:
    async def test_delete_task(self, client: AsyncClient):
        create_resp = await client.post(
            "/tasks", json={"title": "Delete me", "priority": 1, "due_date": _future_date()}
        )
        task_id = create_resp.json()["id"]
        del_resp = await client.delete(f"/tasks/{task_id}")
        assert del_resp.status_code == 204

        # Should not appear in list
        list_resp = await client.get("/tasks")
        task_ids = {t["id"] for t in list_resp.json()["tasks"]}
        assert task_id not in task_ids

        # GET by id should 404
        get_resp = await client.get(f"/tasks/{task_id}")
        assert get_resp.status_code == 404

    async def test_delete_nonexistent_task(self, client: AsyncClient):
        resp = await client.delete("/tasks/99999")
        assert resp.status_code == 404

    async def test_delete_already_deleted(self, client: AsyncClient):
        create_resp = await client.post(
            "/tasks", json={"title": "Double delete", "priority": 1, "due_date": _future_date()}
        )
        task_id = create_resp.json()["id"]
        await client.delete(f"/tasks/{task_id}")
        resp = await client.delete(f"/tasks/{task_id}")
        assert resp.status_code == 404
