import os
from soleclaw.core.pidfile import write_pid, remove_pid, read_pid, is_gateway_running


def test_write_and_read_pid(tmp_path):
    write_pid(tmp_path)
    pid = read_pid(tmp_path)
    assert pid == os.getpid()


def test_remove_pid(tmp_path):
    write_pid(tmp_path)
    remove_pid(tmp_path)
    assert read_pid(tmp_path) is None


def test_read_pid_missing(tmp_path):
    assert read_pid(tmp_path) is None


def test_is_gateway_running_current_process(tmp_path):
    write_pid(tmp_path)
    assert is_gateway_running(tmp_path) is True
    remove_pid(tmp_path)


def test_is_gateway_running_stale(tmp_path):
    (tmp_path / "gateway.pid").write_text("999999999")
    assert is_gateway_running(tmp_path) is False
    assert not (tmp_path / "gateway.pid").exists()


def test_is_gateway_running_no_file(tmp_path):
    assert is_gateway_running(tmp_path) is False
