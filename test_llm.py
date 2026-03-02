from llm_client import LLMClient

client = LLMClient()
print(client.summarize({'structure': 'file1.py\nfile2.py',
                         'readme': 'This is a test README for a sample project.'}))
