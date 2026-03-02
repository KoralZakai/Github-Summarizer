import inspect
from llm_client import LLMClient
source = inspect.getsource(LLMClient.summarize)
for i, line in enumerate(source.splitlines(), 1):
    print(f"{i:03}: {repr(line)}")
