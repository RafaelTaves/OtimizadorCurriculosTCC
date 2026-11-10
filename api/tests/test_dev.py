import subprocess
import sys
from unittest.mock import Mock, patch

import pytest

from app.dev import API_ROOT, run, stop_processes


def test_starts_api_and_worker_with_same_environment_and_stops_on_interrupt():
    children = [Mock(), Mock(), Mock()]
    for child in children:
        child.poll.return_value = None
    with (
        patch("app.dev.subprocess.Popen", side_effect=children) as start,
        patch("app.dev.sleep", side_effect=KeyboardInterrupt),
    ):
        assert run(port=8100) == 0
    api_call, ai_call, pdf_call = start.call_args_list
    assert api_call.args[0] == [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:create_app",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        "8100",
    ]
    assert ai_call.args[0] == [sys.executable, "-m", "app.worker", "--lane", "ai"]
    assert pdf_call.args[0] == [sys.executable, "-m", "app.worker", "--lane", "pdf"]
    assert api_call.kwargs == ai_call.kwargs == pdf_call.kwargs == {"cwd": API_ROOT}
    for child in children:
        child.terminate.assert_called_once()
        child.wait.assert_called_once_with(timeout=5)


@pytest.mark.parametrize("failed_child", [0, 1, 2])
def test_a_service_exit_stops_the_other_service(failed_child):
    children = [Mock(), Mock(), Mock()]
    for index, child in enumerate(children):
        child.poll.return_value = 2 if index == failed_child else None
    with patch("app.dev.subprocess.Popen", side_effect=children):
        assert run() == 2
    children[failed_child].terminate.assert_not_called()
    for index, child in enumerate(children):
        if index != failed_child:
            child.terminate.assert_called_once()


def test_failure_to_start_second_service_does_not_leave_api_running():
    api = Mock()
    api.poll.return_value = None
    with patch("app.dev.subprocess.Popen", side_effect=[api, OSError("cannot start")]):
        with pytest.raises(OSError):
            run()
    api.terminate.assert_called_once()


def test_unresponsive_child_is_killed_after_shutdown_timeout():
    process = Mock()
    process.poll.return_value = None
    process.wait.side_effect = [subprocess.TimeoutExpired("worker", 5), 0]
    stop_processes([process])
    process.terminate.assert_called_once()
    process.kill.assert_called_once()
    assert process.wait.call_count == 2
