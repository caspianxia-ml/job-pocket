# GitHub 发布与维护

建议名称：**JobPocket · 求职信息整理助手**。描述突出本地整理、断点和表格导出。Topics 可选 `python`、`playwright`、`job-search`、`personal-productivity`。

## 第一次发布

1. 运行核心测试和离线浏览器测试，README 中准确注明实站适配状态。不要把合成页面测试描述成真实平台验收。
2. 在 GitHub 创建空仓库，把本项目目录作为仓库根目录；这里没有预设你的账号、远程地址，也没有替你上传。
3. 检查待提交文件再 commit/push。`.gitignore` 只防止新的误提交，不能清除 Git 历史中的文件。

```bash
git init
git add .
git status --short
git diff --cached --stat
git diff --cached
```

检查实际清单应只有程序、文档、测试和配置示例。确认没有 `.private/`、`data/`、`exports/`、`config.local.json`、`.env`、Cookie、浏览器截图、个人 JD 或数据库。若使用了仓库外的 `--workspace`，该目录也不能复制进仓库。

```bash
git commit -m "Initial JobPocket assistant"
```

之后使用 GitHub 页面给出的真实远程地址设置 remote 并 push。无需为运行程序提供 GitHub Token。

## 如果误提交登录状态

立即使相关会话失效，在平台正常退出/撤销相关登录；删除当前文件不足以清除历史凭据。按 GitHub 官方的敏感数据清理流程处理历史与副本。不要把文件复制到 Issue 里请求帮助。

## 接受的贡献

- 脱敏最小页面夹具、选择器修复、字段提取改进。
- 本地筛选、求职笔记、可选来源适配器，但不得自动扩大本次推荐采集范围。
- 数据库迁移和格式兼容测试。

不合并验证码绕过、隐藏接口抓取、签名破解、代理轮换、账号池和批量招呼/投递实现。

## Issue 信息

提交 Python/操作系统版本、停止原因、发生阶段、是否修改过选择器及脱敏的最小结构即可。不要附账号、密码、Cookie、个人登录二维码、完整浏览器日志或带认证参数的 URL。

MIT 仅覆盖本项目代码；第三方内容、名称和商标仍属于相应权利方。
