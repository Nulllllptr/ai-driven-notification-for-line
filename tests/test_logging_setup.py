import json

from src.common import logging_setup


def test_masked_field_is_not_output_in_plain_text(capsys):
    logger = logging_setup.get_logger("test_masking")
    logger.info("using token=SECRET123 to call api")
    output = capsys.readouterr().out.strip().splitlines()[-1]
    payload = json.loads(output)
    assert "SECRET123" not in payload["message"]
    assert "***" in payload["message"]
