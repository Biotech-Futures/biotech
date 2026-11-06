# Local demo tooling / 本地演示工具

Prepared-workstation tooling for the **Admin Analytics and AI chatbot demo** on the LLM demo branch. It is separate from the product runtime and is not a deployment dependency.

这是 LLM 演示分支上用于 **Admin Analytics 与 AI chatbot** 的本地工具，不是产品运行或部署依赖。

## Prerequisites / 使用前提

These launchers target the already prepared macOS demo environment. A fresh clone alone is **not** ready to run. The workstation needs Docker Desktop, Python 3, Node.js 22, Google Chrome and the existing local preview setup:

这些入口针对已配置好的 macOS 演示环境；**仅克隆代码不能直接运行**。需要 Docker Desktop、Python 3、Node.js 22、Google Chrome，以及原有本地预览环境：

- `tmp/llm-preview-20261027-1zyclbhd/.preview.env` and `compose.preview.yml` — private local configuration / 本地私有配置。
- That preview's `frontend/node_modules` and Docker image `biotech-llm-preview:20261027` — prepared dependencies / 已准备的依赖与镜像。
- `tmp/demo-update-20261106/demo-state.json` — selected demo database, created by the prepared environment's setup / 已准备环境生成的当前演示库记录。

Keep private configuration, API keys, database dumps, generated files and dependencies out of Git. Do not copy these prerequisites into the repository to make a new checkout appear complete. The current Windows launcher is legacy tooling and is not the verified demo entry point.

私有配置、API key、数据库备份、生成文件和依赖不得提交。不要为了补齐新 checkout 而上传这些本机材料。现有 Windows 入口属于旧工具，不是本次验收的演示入口。

## Run / 启动

From the repository root, or double-click the `.command` files in Finder:

在仓库根目录运行，或在 Finder 中双击对应 `.command` 文件：

```sh
./tools/local_db/start-demo.command
./tools/local_db/open_gui.command
./tools/local_db/run status
./tools/local_db/run verify
```

The website runs at `http://127.0.0.1:5187/#/analytics`, backend at port `8017`, and this generator at `http://127.0.0.1:8766/`. Launchers open separate Chrome windows. Keep the terminal that runs the website open. Port `8765` belongs to the older generator and is not this demo target.

网站为 `http://127.0.0.1:5187/#/analytics`，后端端口为 `8017`，本生成器为 `http://127.0.0.1:8766/`。入口会打开独立 Chrome 窗口；演示期间保留运行网站的终端。`8765` 属于旧生成器，不是本次演示目标。

## Generate / 生成

- **Manual mode:** configure quantities, email and dates, then use its generation button. **Automatic mode:** enter the student count and ± variation, review the calculated quantities, then use its separate generation button. Switching modes preserves both forms.
- **手动模式：**逐项配置数量、邮件和时间，再使用本模式的生成按钮。**自动模式：**填写学生数与 ± 浮动比例，检查数量预览，再使用独立生成按钮。切换模式不会覆盖两边输入。
- Every confirmed generation **clears and rebuilds the selected local `biotech_llm_demo_*` database**, including sessions and extra records. The rebuild rolls back on failure. Other databases are not reset, and generation sends no email. Reload the website and sign in again after success.
- 每次确认生成都会**清空并重建当前选中的本地 `biotech_llm_demo_*` 数据库**，包括会话及额外记录；失败会回滚。其他数据库不会被清空，生成过程不会发邮件。成功后刷新网站并重新登录。

Demo sign-in / 演示登录：

- Admin: `synthetic.admin.0001@team4-synthetic.biotech.test` / `admin123`
- Student: `synthetic.student.0001@team4-synthetic.biotech.test` / `student123`

See [DEMO_GUIDE_ZH.txt](DEMO_GUIDE_ZH.txt) and the GUI's bilingual usage guide for details. Real AI responses still depend on the existing private key and network; the local FAQ fallback is not a live model call.

详细操作见 [DEMO_GUIDE_ZH.txt](DEMO_GUIDE_ZH.txt) 及界面内的中英文指南。真实 AI 回复仍依赖原有私密 key 和网络；本地 FAQ 回退不能视为真实模型调用。

## Validation / 验证范围

`./tools/local_db/run test` runs the tool tests in the prepared Docker environment. Recorded verification on 2026-11-06: 82 tests passed, with 2 destructive reset integration tests skipped in the latest run; those reset tests had passed separately on a disposable test database. A 1,000-student ±10% dataset was also generated and checked in an isolated database, including relationships, fingerprints, recipient totals and demo passwords. These results describe that prepared environment, not acceptance of a fresh checkout or Windows setup.

`./tools/local_db/run test` 在已准备的 Docker 环境中执行工具测试。2026-11-06 的验证记录：最新一轮 82 项通过，2 项完整清库集成测试跳过；清库测试此前已在独立测试库通过。另已在隔离库实际生成 1,000 学生、±10% 数据，并校验关联关系、指纹、收件人总量及演示密码。这些记录针对已准备环境，不代表已验收全新 checkout 或 Windows 安装流程。
