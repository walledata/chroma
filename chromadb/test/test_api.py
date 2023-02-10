import chromadb
from chromadb.config import Settings
import chromadb.server.fastapi
import pytest
import time
import tempfile
import copy
import os
from multiprocessing import Process
import uvicorn
from requests.exceptions import ConnectionError

@pytest.fixture
def local_api():
    return chromadb.Client(Settings(chroma_api_impl="local",
                                   chroma_db_impl="duckdb",
                                   persist_directory=tempfile.gettempdir()))

@pytest.fixture
def fastapi_integration_api():
    return chromadb.Client() # configured by environment variables


def _build_fastapi_api():
    return chromadb.Client(Settings(chroma_api_impl="rest",
                                   chroma_server_host="localhost",
                                   chroma_server_http_port="6666"))


@pytest.fixture
def fastapi_api():
    return _build_fastapi_api()


def run_server():
    settings = Settings(chroma_api_impl="local",
                        chroma_db_impl="duckdb",
                        persist_directory=tempfile.gettempdir()+"/test_server")
    server = chromadb.server.fastapi.FastAPI(settings)
    uvicorn.run(server.app(), host="0.0.0.0", port=6666, log_level="info")


def await_server(attempts=0):
    api = _build_fastapi_api()

    try:
        api.heartbeat()
    except ConnectionError as e:
        if attempts > 10:
            raise e
        else:
            time.sleep(2)
            await_server(attempts + 1)


@pytest.fixture(scope="module", autouse=True)
def fastapi_server():
    proc = Process(target=run_server, args=(), daemon=True)
    proc.start()
    await_server()
    yield
    proc.kill()

test_apis = [local_api, fastapi_api]

if 'CHROMA_INTEGRATION_TEST' in os.environ:
    print("Including integration tests")
    test_apis.append(fastapi_integration_api)


@pytest.mark.parametrize('api_fixture', test_apis)
def test_heartbeat(api_fixture, request):
    api = request.getfixturevalue(api_fixture.__name__)

    assert isinstance(api.heartbeat(), int)


batch_records = {"embeddings": [[1.1, 2.3, 3.2], [1.2, 2.24, 3.2]],
                 "ids": ["https://example.com", "https://example.com"],
                 }

@pytest.mark.parametrize('api_fixture', test_apis)
def test_add(api_fixture, request):
    api = request.getfixturevalue(api_fixture.__name__)

    api.reset()

    collection = api.create_collection("testspace")

    collection.add(**batch_records)

    assert collection.count() == 2


minimal_records = {"embeddings": [[1.1, 2.3, 3.2], [1.2, 2.24, 3.2]],
                   "ids": ["https://example.com", "https://example.com"],
                   }


@pytest.mark.parametrize('api_fixture', test_apis)
def test_add_minimal(api_fixture, request):
    api = request.getfixturevalue(api_fixture.__name__)

    api.reset()

    collection = api.create_collection("testspace")

    collection.add(**minimal_records)

    assert collection.count() == 2


@pytest.mark.parametrize('api_fixture', test_apis)
def test_get_from_db(api_fixture, request):
    api = request.getfixturevalue(api_fixture.__name__)

    api.reset()
    collection = api.create_collection("testspace")
    collection.add(**batch_records)
    records = collection.get()

    assert len(records) == 2


@pytest.mark.parametrize('api_fixture', test_apis)
def test_reset_db(api_fixture, request):
    api = request.getfixturevalue(api_fixture.__name__)

    api.reset()

    collection = api.create_collection("testspace")
    collection.add(**batch_records)
    assert collection.count() == 2

    assert api.reset()
    # assert collection.count() == 0


@pytest.mark.parametrize('api_fixture', test_apis)
def test_get_nearest_neighbors(api_fixture, request):
    api = request.getfixturevalue(api_fixture.__name__)

    api.reset()
    collection = api.create_collection("testspace")
    collection.add(**batch_records)
    # assert api.create_index(collection_name="testspace") # default is auto now

    nn = collection.query(query_embeddings=[[1.1, 2.3, 3.2]],
                                   n_results=1,
                                   where={})

    print("nn", nn)
    assert len(nn[0]['items']) == 1


@pytest.mark.parametrize('api_fixture', test_apis)
def test_get_nearest_neighbors_filter(api_fixture, request):
    api = request.getfixturevalue(api_fixture.__name__)

    api.reset()
    collection = api.create_collection("testspace")
    collection.add(**batch_records)

    # assert api.create_index(collection_name="testspace") # default is auto now

    with pytest.raises(Exception) as e:
        nn = collection.query(query_embeddings=[[1.1, 2.3, 3.2]],
                                       n_results=1,
                                       where={"distance":"false"})

    assert str(e.value).__contains__("found")


@pytest.mark.parametrize('api_fixture', test_apis)
def test_delete(api_fixture, request):
    api = request.getfixturevalue(api_fixture.__name__)

    api.reset()
    collection = api.create_collection("testspace")
    collection.add(**batch_records)
    assert collection.count() == 2

    # generic delete on collection not working yet
    # assert collection.delete() == []
    # assert collection.count() == 2
    # assert collection.delete()
    # assert collection.count() == 0


@pytest.mark.parametrize('api_fixture', test_apis)
def test_delete_with_index(api_fixture, request):
    api = request.getfixturevalue(api_fixture.__name__)

    api.reset()
    collection = api.create_collection("testspace")
    collection.add(**batch_records)
    assert collection.count() == 2
    # api.create_index()
    nn = collection.query(query_embeddings=[[1.1, 2.3, 3.2]],
                                   n_results=1)


    # assert nn['embeddings']['inference_class'][0] == 'knife'

    # assert api.delete(where={"inference_class": "knife"})

    # nn2 = api.get_nearest_neighbors(embedding=[1.1, 2.3, 3.2],
    #                                 n_results=1)
    # assert nn2['embeddings']['inference_class'][0] == 'person'
