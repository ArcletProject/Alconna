from tests.analyser_test import *
from tests.args_test import *
from tests.base_test import *
from tests.components_test import *
from tests.config_test import *
from tests.core_test import *
from tests.util_test import *

if __name__ == '__main__':
    import pytest
    pytest.main([__file__, "-v", "--durations=0"])


