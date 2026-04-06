from openai import OpenAI
from .config import Setting


class LLMConnector(OpenAI):
    def __init__(self):
        OpenAI.__init__(
            self, api_key=Setting.API_KEY.value, base_url=Setting.BASE_URL.value
        )
