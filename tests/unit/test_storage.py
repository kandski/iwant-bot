import os

import pytest
import datetime

from iwant_bot import storage, requests, storage_sqlalchemy


NOW = datetime.datetime.now()
TIME_1MIN = datetime.timedelta(minutes=1)


def make_request_stacker(store):
    def stack_request(uid, person, activity, args=(NOW, NOW + 5 * TIME_1MIN, 60 * 5)):
        request = requests.IWantRequest(person, activity, * args)
        request.id = uid
        request = store.store_request(request)
        return request
    return stack_request


def test_memory_storage_saves_and_restores():
    store = storage.MemoryRequestsStorage()
    storage_saves_and_restores(store)


def storage_saves_and_restores(store):
    store.wipe_database()
    stack = make_request_stacker(store)

    request = stack("one", "john", "coffee")
    recovered_request = store.get_activity_requests()[0]
    assert request == recovered_request
    with pytest.raises(ValueError) as err:
        store.store_request(42)
    assert "int" in str(err)
    corresponding_result = store.get_result(recovered_request.resolved_by)
    assert corresponding_result.status == requests.Status.PENDING


def test_storage_sqlite_saves_and_restores():
    store = storage_sqlalchemy.SqlAlchemyRequestStorage("sqlite:///here.sqlite")
    storage_saves_and_restores(store)


@pytest.fixture()
def postgres_store():
    username = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]
    store = storage_sqlalchemy.SqlAlchemyRequestStorage(
        f"postgresql+psycopg2://{username}:{password}@postgres/{username}")
    return store


@pytest.mark.skipif("POSTGRES_USER" not in os.environ,
                    reason="Postgres container connection is not configured correctly")
def test_storage_postgres_saves_and_restores(postgres_store):
    storage_saves_and_restores(postgres_store)


def test_memory_storage_removes():
    store = storage.MemoryRequestsStorage()
    storage_removes(store)


def test_sqlite_storage_removes():
    store = storage_sqlalchemy.SqlAlchemyRequestStorage("sqlite:///here.sqlite")
    storage_removes(store)


@pytest.mark.skipif("POSTGRES_USER" not in os.environ,
                    reason="Postgres container connection is not configured correctly")
def test_postgres_storage_removes(postgres_store):
    storage_removes(postgres_store)


def test_memory_storage_resolves_and_fetches():
    store = storage.MemoryRequestsStorage()
    storage_resolves_and_fetches(store)


def test_sqlite_storage_resloves():
    store = storage_sqlalchemy.SqlAlchemyRequestStorage("sqlite:///here.sqlite")
    storage_resolves_and_fetches(store)


@pytest.mark.skipif("POSTGRES_USER" not in os.environ,
                    reason="Postgres container connection is not configured correctly")
def test_postgres_storage_removes(postgres_store):
    storage_resolves_and_fetches(postgres_store)


def storage_resolves_and_fetches(store):
    store.wipe_database()
    stack = make_request_stacker(store)

    stack("one", "john", "coffee")
    stack("two", "john", "coffee")
    stack("three", "john", "coffee")

    store.resolve_requests(["one", "two"])
    resolved_requests = store.get_activity_requests("coffee")
    resolved_requests = list(filter(lambda r: r.id in ("one", "two"), resolved_requests))
    coffee_result_id = resolved_requests[0].resolved_by
    assert coffee_result_id is not None
    assert coffee_result_id == resolved_requests[1].resolved_by

    store.resolve_requests(["three", "one", "two"])
    resolved_requests = store.get_activity_requests("coffee")
    for req in resolved_requests:
        assert req.resolved_by == coffee_result_id

    picnic_one = stack("four", "jack", "picnic")
    picnic_two = stack("five", "anna", "picnic")
    store.resolve_requests(["four", "five"])

    resolved_requests = store.get_activity_requests("picnic")
    picnic_result_id = resolved_requests[0].resolved_by
    assert picnic_result_id is not None
    assert picnic_result_id == resolved_requests[1].resolved_by
    assert picnic_result_id != coffee_result_id
    result = store.get_result(picnic_result_id)
    assert "four" in result.requests_ids
    assert "five" in result.requests_ids

    requests = store.get_requests_of_result(picnic_result_id)
    assert len(requests) == 2
    picnic_one.resolved_by = picnic_two.resolved_by = picnic_result_id
    assert picnic_one in requests
    assert picnic_two in requests


def storage_removes(store):
    store.wipe_database()
    stack = make_request_stacker(store)

    stack("one", "john", "coffee")
    to_be_removed = stack("foo", "john", "coffee")

    with pytest.raises(AssertionError):
        store.remove_activity_request("bar", "jack")
    with pytest.raises(AssertionError):
        store.remove_activity_request("foo", "jack")
    store.remove_activity_request("foo", "john")
    assert len(store.get_activity_requests()) == 1
    removed_result_id = to_be_removed.resolved_by
    assert store.get_result(removed_result_id).status == requests.Status.INVALID


def storage_removes_resolved_requests(store):
    store.wipe_database()
    stack = make_request_stacker(store)

    first_result_id = stack("one", "john", "coffee",
                            (NOW, NOW + 5 * TIME_1MIN, 60 * 5)).resolved_by
    second_result_id = stack("foo", "john", "coffee",
                             (NOW + TIME_1MIN, NOW + 10 * TIME_1MIN, 60 * 5)).resolved_by
    result_ids = {first_result_id, second_result_id}
    assert len(result_ids) == 2

    result_id = store.resolve_requests(["one", "foo"])
    assert result_id in result_ids
    purged_result_id = (result_ids - {result_id, }).pop()

    result = store.get_result(purged_result_id)
    assert result.status == requests.Status.INVALID

    result = store.get_result(result_id)
    assert result.status == requests.Status.FRESH
    assert result.deadline == NOW
    store.remove_activity_request("one", "john")

    result = store.get_result(result_id)
    assert result.status == requests.Status.PENDING
    assert result.deadline == NOW + TIME_1MIN


def test_memory_storage_removes_resolved_requests():
    store = storage.MemoryRequestsStorage()
    storage_removes_resolved_requests(store)


def test_sqlite_storage_removes_resolved_requests():
    store = storage_sqlalchemy.SqlAlchemyRequestStorage("sqlite:///here.sqlite")
    storage_removes_resolved_requests(store)


@pytest.mark.skipif("POSTGRES_USER" not in os.environ,
                    reason="Postgres container connection is not configured correctly")
def test_postgres_storage_removes_resolved_requests(postgres_store):
    storage_removes_resolved_requests(postgres_store)


def test_memory_storage_understands_time():
    store = storage.MemoryRequestsStorage()
    storage_understands_time(store)


def test_sqlite_storage_understands_time():
    store = storage_sqlalchemy.SqlAlchemyRequestStorage("sqlite:///here.sqlite")
    storage_understands_time(store)


def storage_understands_time(store):
    store.wipe_database()
    stack = make_request_stacker(store)

    early_deadline = NOW + TIME_1MIN * 0.8
    mid_deadline = NOW + TIME_1MIN
    stack("one", "john", "coffee", (early_deadline, NOW, 0))
    stack("two", "janine", "tea", (mid_deadline, NOW, 0))
    stack("three", "paul", "wine", (NOW + TIME_1MIN * 1.2, NOW, 0))

    expiring_requests = store.get_requests_by_deadline_proximity(NOW + 2 * TIME_1MIN, 58)
    assert len(expiring_requests) == 1
    expiring_requests.pop().id == "three"

    expiring_requests = store.get_requests_by_deadline_proximity(NOW + 2 * TIME_1MIN, 62)
    assert len(expiring_requests) == 2
    for req in expiring_requests:
        assert req.id in ("three", "two")

    result_id = store.resolve_requests(["three", "two"])
    result = store.get_result(result_id)
    assert result.deadline == mid_deadline


def test_memory_storage_filters_activities():
    store = storage.MemoryRequestsStorage()
    storage_filters_activities(store)


@pytest.mark.skipif("POSTGRES_USER" not in os.environ,
                    reason="Postgres container connection is not configured correctly")
def test_postgres_storage_understands_time(postgres_store):
    storage_understands_time(postgres_store)


def test_sqlite_storage_filters_activities():
    store = storage_sqlalchemy.SqlAlchemyRequestStorage("sqlite:///here.sqlite")
    storage_filters_activities(store)


@pytest.mark.skipif("POSTGRES_USER" not in os.environ,
                    reason="Postgres container connection is not configured correctly")
def test_postgres_storage_filters_activities(postgres_store):
    storage_filters_activities(postgres_store)


def storage_filters_activities(store):
    store.wipe_database()
    stack = make_request_stacker(store)

    stack("1", "john", "coffee")
    stack("2", "jack", "coffee")
    stack("3", "jane", "tea")

    recovered_tea_requests = store.get_activity_requests("tea")
    assert len(recovered_tea_requests) == 1
    assert recovered_tea_requests[0].person_id == "jane"

    recovered_coffee_requests = store.get_activity_requests("coffee")
    assert len(recovered_coffee_requests) == 2

    recovered_all_requests = store.get_activity_requests()
    assert len(recovered_all_requests) == 3
