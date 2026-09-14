from agentdist.structures.dataobject import RunTimeConfig, UDFConfig
from function_schema import get_function_schema


def udf(env: RunTimeConfig | None = None):
    _env = env

    def __inner(_func):
        nonlocal _env
        func_ser = get_function_schema(_func)
        func_ser["code"] = _func
        _config = UDFConfig(
            name=_func.__name__, func_code=func_ser, runtime_config=_env
        )
        return _config

    return __inner
