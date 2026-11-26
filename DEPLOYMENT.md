# 每日轮播 HTML → GitHub Pages

本地每日任务生成并验收正式文件后运行上传脚本；上传触发 GitHub Actions，发布固定 Pages 地址。GitHub 托管的运行器不能直接读取这台电脑，因此没有单独的定时 cron：上传与生成成功绑定，避免发布昨天的副本。

## 首次配置

1. 创建专用 GitHub 仓库，默认分支为 `main`，勾选创建 README。
2. 仓库 Settings → Pages → Source 选择 **GitHub Actions**。普通 Pages 页面公开可见，请确认允许公开轮播内容。私有仓库使用 Pages 的资格取决于 GitHub 套餐，仓库私有不代表页面私有。
3. 创建仅限这个仓库的 fine-grained token，授予 Contents: Read and write、Workflows: Read and write（首次安装 workflow 需要）。不要把令牌发到聊天、写入 HTML、脚本或仓库。
4. 在运行每日生成任务的进程环境中设置 `GITHUB_TOKEN`。脚本不会保存令牌。可以设置 `CAROUSEL_GITHUB_REPO=OWNER/REPO`，也可以每次传 `--repo`。
5. 正式文件生成并通过验收后，首次执行：

```powershell
python .\github-carousel\upload_latest.py --file .\FBA-PST2-sprint-carousel.html --repo OWNER/REPO --bootstrap
```

首次上传同时安装 `.github/workflows/pages.yml`。之后每日生成任务只需执行：

```powershell
python .\github-carousel\upload_latest.py --file .\FBA-PST2-sprint-carousel.html --repo OWNER/REPO
```

首次部署成功后的地址由 Actions 的部署结果提供，通常为 `https://OWNER.github.io/REPO/`。主文件固定为 `site/index.html`；发布产物只有 `index.html` 和 `.nojekyll`。

## 自动生成任务接入规则

保留现有生成、数据重读、视觉验收和失败保护要求。在正式 HTML 本次生成、验收、保存成功之后，执行上面的每日上传命令。不要上传 `.carousel-work/candidate.html` 或因生成失败而沿用的旧文件。缺少令牌或仓库配置时报告未上传，不索取或记录凭据。上传失败不删除本地正式文件，也不先删除线上版本；报告失败并稍后重试。脚本退出 0 表示内容已上传或已经相同，不表示 Pages 已部署完成，需核对 Actions 的部署结果。

## 历史清理范围

上传脚本会在同一次 Git 提交中覆盖 `site/index.html` 并删除 `site/` 内其他 `.html` 文件，保留目录外所有文件。不会删除仓库、工作流或其他数据，也不会改写 Git 提交历史。Pages 每次使用只含最新 HTML 的全新发布产物；旧 Actions 日志、artifact 的保留由 GitHub 设置管理。曾提交的内容仍可能从 Git 历史恢复，敏感内容不能依靠删除旧文件撤回公开披露。

## 验证

```powershell
python -m unittest discover -s .\github-carousel -p 'test_*.py'
python .\github-carousel\upload_latest.py --file .\FBA-PST2-sprint-carousel.html --dry-run
```

其他电脑打开 Pages 地址即可查看。已打开的页面是否自动热更新取决于正式 HTML 的刷新逻辑，部署流程不会自动改写播放器。若浏览器显示旧内容可先手动刷新；定时检查更新需要在正式播放器中验证。
