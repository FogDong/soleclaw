from soleclaw.channels.base import BaseChannel


def test_base_channel_is_abstract():
    import pytest
    with pytest.raises(TypeError):
        BaseChannel(config=None, bus=None)
