from unittest.mock import patch
import pytest
from claude_hub.service import factory


def test_unknown_os_raises():
    with patch("claude_hub.platform.detect.current_os", return_value="unknown"):
        with pytest.raises(RuntimeError, match="unsupported"):
            factory.get_service_manager(prefer="auto")
