import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from link import Link          # noqa: E402
from mock_server import MockServer   # noqa: E402


def pytest_addoption(parser):
    parser.addoption("--port", default=os.environ.get("GAME_PORT", "mock"),
                     help="'mock', a COM port / device, or a pyserial URL (env GAME_PORT)")
    parser.addoption("--mock-fault", default=os.environ.get("MOCK_FAULT", ""),
                     help="inject a fault into the mock (used by mutation_check.py)")


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: waits for protocol timeouts")


@pytest.fixture(scope="session")
def port_url(request):
    port = request.config.getoption("--port")
    if port != "mock":
        yield port
        return
    fault = request.config.getoption("--mock-fault")
    server = MockServer(faults=[fault] if fault else []).start()
    yield server.url
    server.stop()


@pytest.fixture
def link(port_url):
    lk = Link(port_url)
    lk.sync_to_idle()
    yield lk
    try:
        lk.sync_to_idle()
    finally:
        lk.close()
