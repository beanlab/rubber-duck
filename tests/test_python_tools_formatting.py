import pandas as pd
import sys
import types
import asyncio


boto3_stub = types.ModuleType("boto3")
boto3_stub.client = lambda *_args, **_kwargs: types.SimpleNamespace()
sys.modules.setdefault("boto3", boto3_stub)

botocore_stub = types.ModuleType("botocore")
botocore_exceptions_stub = types.ModuleType("botocore.exceptions")


class _ClientError(Exception):
    pass


botocore_exceptions_stub.ClientError = _ClientError
botocore_stub.exceptions = botocore_exceptions_stub
sys.modules.setdefault("botocore", botocore_stub)
sys.modules.setdefault("botocore.exceptions", botocore_exceptions_stub)

from src.armory.python_tools import _format_table_values, send_table


def test_format_table_values_rounds_and_trims_numeric_columns():
    table = pd.DataFrame(
        {
            "value": [28.300000000001, 1.23456, 2.0],
            "label": ["a", "b", "c"],
        }
    )

    formatted = _format_table_values(table)

    assert formatted["value"].tolist() == ["28.3", "1.2346", "2"]
    assert formatted["label"].tolist() == ["a", "b", "c"]


def test_format_table_values_keeps_blank_for_missing_numeric_values():
    table = pd.DataFrame({"value": [1.2, None]})

    formatted = _format_table_values(table)

    assert formatted["value"].tolist() == ["1.2", ""]


def test_format_table_values_expands_scientific_notation_and_rounds():
    table = pd.DataFrame({"value": [1.23016e+07]})

    formatted = _format_table_values(table)

    assert formatted["value"].tolist() == ["12301600"]


def test_send_table_does_not_reintroduce_scientific_notation():
    table = pd.DataFrame(
        {
            "conf_low": [-3.71812e08, -40746, 99701.2],
            "conf_high": [-1.97874e08, 332304, 2.45405e06],
        }
    )
    sent_messages = []

    async def _send_message(_channel_id, message=None, file=None):
        if message is not None:
            sent_messages.append(message)
        if file is not None:
            sent_messages.append(str(file))

    asyncio.run(send_table(_send_message, 123, table))

    rendered = "\n".join(sent_messages)
    assert "-3.71812e+08" not in rendered
    assert "-1.97874e+08" not in rendered
    assert "2.45405e+06" not in rendered
    assert "-371812000" in rendered
    assert "-197874000" in rendered
    assert "2454050" in rendered
