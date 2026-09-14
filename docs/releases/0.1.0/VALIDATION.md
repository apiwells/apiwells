# ApiWells 0.1.0 验证记录

验证日期：2026-09-07。环境：Linux / CPython 3.12.13。

## 已完成

- PyPI JSON 查询：`https://pypi.org/pypi/apiwells/json` 返回 HTTP 404。
  只表示本次未查到公开项目，不保证名称可用。
- `python -m build apiwells`：成功生成 sdist，再从 sdist 构建 wheel。
- `twine check --strict`：两个分发文件均 PASSED。
- 全新 .verify-env 环境以 `--no-index --no-deps` 安装最终 wheel 成功。
- 确认导入来源位于该环境 site-packages，而非源码开发目录。
- 在这个仅安装 wheel 的环境执行 11 项 unittest：全部通过。
- `python -m apiwells --version` 和安装生成的 `apiwells doctor --help` 成功。
- `pip check`：No broken requirements found。

## 测试范围

本地真实 HTTP 服务覆盖模型列表、POST 对话及请求参数、401/403/404/405/
400/429/500 分类、禁止重定向、无自动重试、无效 JSON、错误结构、
200 错误封装、超大响应、超时、配置错误、缺少密钥、代理默认关闭、
JSON/退出码以及响应中模拟密钥不进入报告。

11 是测试方法数量；部分方法包含多个子场景。
详细结果见 validation-tests.txt；打包检查见 validation-packaging.txt。

## 尚未验证

- 没有使用真实商业上游端点或真实密钥。
- 未对 HTTPS 证书链和 DNS 故障做独立集成测试；TLS 验证依赖标准库默认行为。
- 未进行 Windows、macOS 或其他 Python 版本实机测试。
- 未进行 TestPyPI/PyPI 认证上传，未确认项目所有权。
- 不是完整协议兼容性、性能、模型质量或安全审计报告。

下一步按 apiwells/docs/PUBLISH_ZH.md 在维护者本机完成真实端点验收、
TestPyPI 和正式发布，最后从正式索引全新安装。这些步骤完成后才能
声称 `pip install apiwells` 已在 PyPI 对公众可用。
