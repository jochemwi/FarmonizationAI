import pytest

def test_bash_runs_command_and_returns_output():
    from src.tools.tools import bash

    result = bash.invoke({"command": "echo hello", "description": "print hello"})

    assert "hello" in result


def test_bash_returns_error_on_bad_command():
    from src.tools.tools import bash

    result = bash.invoke({"command": "cat nonexistent_file.txt", "description": "read missing file"})

    assert "exit code" in result


def test_bash_truncates_large_output():
    from src.tools.tools import bash

    # generate output larger than MAX_OUTPUT (4000 chars)
    result = bash.invoke({"command": "python3 -c \"print('a' * 10000)\"", "description": "generate large output"})

    assert "truncated" in result
    assert len(result) < 10000

@pytest.mark.slow
def test_bash_timeout():
    from src.tools.tools import bash

    result = bash.invoke({"command": "sleep 120", "description": "sleep forever"})

    assert "timed out" in result