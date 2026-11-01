import pytest


def pytest_addoption(parser):
    parser.addoption("--run-browser", action="store_true", default=False,
                     help="运行本地浏览器夹具测试；需要 playwright install chromium")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-browser"):
        return
    for item in items:
        if "browser" in item.keywords:
            item.add_marker(pytest.mark.skip(reason="添加 --run-browser 运行完全离线的浏览器测试"))
