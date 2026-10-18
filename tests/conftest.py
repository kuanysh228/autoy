import os
import tempfile

os.environ["AUTOY_HOME"] = tempfile.mkdtemp(prefix="autoy-tests-")
