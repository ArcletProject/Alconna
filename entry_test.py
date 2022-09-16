from test_alconna.args_test import *
from test_alconna.base_test import *
from test_alconna.util_test import *
from test_alconna.core_test import *
from test_alconna.components_test import *
from test_alconna.config_test import *
from test_alconna.analyser_test import *

if __name__ == '__main__':
    import pytest
    pytest.main([__file__, "-v"])
