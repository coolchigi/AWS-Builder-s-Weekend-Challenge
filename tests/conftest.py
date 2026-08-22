"""Test bootstrap: put src/ on the path and stub AWS SDK imports.

The modules create boto3 clients at import time. Stubbing boto3/botocore lets
the pure logic (prompts, rendering, parsing, validation) be tested without the
SDK installed or any AWS credentials.
"""

import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

_boto3 = types.ModuleType("boto3")
_boto3.client = lambda *a, **k: types.SimpleNamespace()
_boto3.resource = lambda *a, **k: types.SimpleNamespace()
sys.modules.setdefault("boto3", _boto3)

_botocore = types.ModuleType("botocore")
_config = types.ModuleType("botocore.config")
_config.Config = lambda *a, **k: None
_botocore.config = _config
sys.modules.setdefault("botocore", _botocore)
sys.modules.setdefault("botocore.config", _config)
