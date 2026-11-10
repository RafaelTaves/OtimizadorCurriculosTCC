import subprocess
import sys
from unittest.mock import Mock, patch

import pytest

from app.dev import API_ROOT, run, stop_processes


def test_starts_api_and_worker_with_same_environment_and_stops_on_interrupt():
    api, worker = Mock(), Mock()
    api.poll.return_value = worker.poll.return_value = None
    with (
        patch("app.dev.subprocess.Popen", side_effect=[api, worker]) as start,
        patch("app.dev.sleep", side_effect=KeyboardInterrupt),
    ):
        assert run(port=8100) == 0
    api_call, worker_call = start.call_args_list
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
    assert worker_call.args[0] == [sys.executable, "-m", "app.worker"]
    assert api_call.kwargs == worker_call.kwargs == {"cwd": API_ROOT}
    api.terminate.assert_called_once()
    worker.terminate.assert_called_once()
    api.wait.assert_called_once_with(timeout=5)
    worker.wait.assert_called_once_with(timeout=5)


@pytest.mark.parametrize("failed_child", [0, 1])
def test_a_service_exit_stops_the_other_service(failed_child):
    children = [Mock(), Mock()]
    children[failed_child].poll.return_value = 2
    children[1 - failed_child].poll.return_value = None
    with patch("app.dev.subprocess.Popen", side_effect=children):
        assert run() == 2
    children[failed_child].terminate.assert_not_called()
    children[1 - failed_child].terminate.assert_called_once()


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
