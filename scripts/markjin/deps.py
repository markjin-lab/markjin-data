"""运行依赖检查（整体验收 r10 MEDIUM）。markjin 依赖 PyYAML（见 requirements.txt），其余只用标准库。

缺 PyYAML 时不得直接抛 ModuleNotFoundError：selfcheck 记 E-DEP-PYYAML（硬错误），route 抛 DependencyError
（RuntimeError 子类，消息以错误码开头），CLI 输出结构化 HOLD、非零退出。"""

DEP_CODE = "E-DEP-PYYAML"


class DependencyError(RuntimeError):
    pass


def have_yaml():
    try:
        import yaml  # noqa: F401
    except ImportError:
        return False
    return True


def require_yaml():
    try:
        import yaml
    except ImportError as e:
        raise DependencyError(f"{DEP_CODE}: 缺少 PyYAML（pip install -r requirements.txt）：{e}") from None
    return yaml
