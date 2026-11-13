"""Official cTrader Open API message definitions and their generated Python code.

The four .proto files are copied unchanged from
https://github.com/spotware/openapi-proto-messages (branch main, fetched 2026-11-12).
The *_pb2.py files were generated from them with grpcio-tools 1.85.1 (protoc for
protobuf 7.35) and need the protobuf runtime pinned in requirements.txt. The only
edit to the generated files: their imports of each other were made relative
("from . import X_pb2") so they load inside this package.

To regenerate after Spotware changes the messages:
    python -m grpc_tools.protoc -I. --python_out=. *.proto
then make the imports relative again (sed -E 's/^import (OpenApi[A-Za-z]+_pb2) as/from . import \\1 as/').
"""
