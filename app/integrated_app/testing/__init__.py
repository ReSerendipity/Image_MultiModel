"""testing — 测试支撑子包（仅测试使用的假引擎等）。

生产环境不会导入本包；FakeEngine 仅当环境变量 IMM_FAKE_ENGINE=1 时
由 model_registry.create_engine_instance 返回，未设置该变量则永不生效。
"""
