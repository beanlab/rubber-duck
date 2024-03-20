import asyncio
import unittest
from unittest.mock import patch, AsyncMock
import pytest
import openai
from rubber_duck import RubberDuck
import httpx

# class TestRetryGetCompletion(unittest.TestCase):
#     async def test_get_completion_with_retry_error_handling(self):
#         with patch('rubber_duck.RubberDuck.get_completion_with_retry', new_callable=AsyncMock) as mock_method:
#             mock_method.side_effect = Exception("Test exception")

@pytest.fixture(scope="module")
def mock_get_completion(mocker):
    async_mock = AsyncMock()
    mocker.patch('rubber_duck._get_completion', new=async_mock)
    return async_mock

@pytest.fixture(scope="module")
def rubber_duck():
    return RubberDuck()

@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.mark.asyncio
async def test_get_completion_with_retry_retries_on_exceptions(rubber_duck, mock_get_completion):
    mock_request = httpx.Request(method="GET", url="https://example.com")

    # Create a mock response object
    mock_response = httpx.Response(
        status_code=404,
        request=mock_request,
        content=b'{"error": "Beep Beep"}'
    )
    raise openai.InternalServerError("Error", response=mock_response, body="yolo")
    raise openai.NotFoundError("Error", response=mock_response, body="yolo")


    exception = openai.InternalServerError("Error", response=mock_response, body="yolo")
    mock_get_completion.side_effect = [exception,
                                       {"choices": [{"message": {"content": "mocked response"}}], "usage": {}}]

    choices, usage = await rubber_duck._get_completion_with_retry(thread_id=123, engine="gpt-4", message_history=[])

    assert mock_get_completion.call_count == 2, "Expected _get_completion to be called twice (initial call + 1 retry)"
    assert choices == [{"message": {"content": "mocked response"}}], "Unexpected choices in response"
    assert usage == {}, "Unexpected usage in response"


if __name__ == '__main__':
    unittest.main()
