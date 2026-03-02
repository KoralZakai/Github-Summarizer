import base64
encoded = base64.b64encode(b"Hello world").decode()
print(encoded)
print(base64.b64decode(encoded).decode())
