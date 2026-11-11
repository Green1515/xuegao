# 学稿 · xuegao

**先学习历史成稿，再直接写出尽量少改的稿件；后续人工修改自动成为增量学习依据。**

这是一个可用于OpenClaw、Codex和Claude Code的Agent Skill。原名creator-calibration，0.2.0起改为短名`xuegao`，中文名“学稿”。

## 用起来是什么样

把视频号/抖音已取得的文字稿、Word或其他可读文档交给agent，直接说：

```text
学稿，学习我上传的这些历史稿件。
本次用新素材……写一条约40秒口播。
按我的写法直接给稿，不用先问我是什么风格。
```

不需要先填风格问卷，也不需要手工写规则JSON。模型会读取已有材料、分型去重、提炼原文支持的写法，选相近范例，在交付前做一次内部对照。有权限时保存风格并同步当前账号的SOUL.md、MEMORY.md和STYLE.md管理区块。

之后作者亲改稿、上传修订版，或应用回传可信编辑保存事件时，自动比较改前改后，吸收表达和结构变化；用户不必另说一次“请记住”。事实更正不自动变成文风，AI自己生成的稿件不当作作者新证据。

**少改是目标，不是已验证的保证。** 多篇共同支持的写法自动生效；单篇也立即作为暂定参考，避免把偶然表达固化。

## 支持什么输入

- TXT、Markdown、DOCX：配套标准库脚本可直接提取、去重和存储。
- 视频号/抖音：复用所在环境已授权的采集和转写能力，已有文字稿直接使用；skill本身不内置平台下载器。
- PDF等：调用当前环境可用的文档解析工具；不能可靠提取时说明缺口，不假装已读。

## 安装

OpenClaw 可通过下方 ClawHub 命令直接安装；Codex、Claude Code 或本地安装方式先取得仓库：

```sh
git clone https://github.com/Green1515/xuegao.git
cd xuegao
```

目标已有同名skill时先比较版本，以下命令不覆盖已存在目录。

### Codex

```sh
mkdir -p ~/.agents/skills
test ! -e ~/.agents/skills/xuegao && cp -R skills/xuegao ~/.agents/skills/
```

调用：`使用 $xuegao，学习我的历史稿件并完成本次创作。`

项目安装放到`.agents/skills/xuegao/`。见[官方文档](https://learn.chatgpt.com/docs/build-skills)。

### Claude Code

```sh
mkdir -p ~/.claude/skills
test ! -e ~/.claude/skills/xuegao && cp -R skills/xuegao ~/.claude/skills/
```

调用：`/xuegao 学习这些历史稿件，按我的写法写新稿。`

项目安装放到`.claude/skills/xuegao/`。本地安装不等于云端同步。见[官方文档](https://code.claude.com/docs/en/skills)。

### OpenClaw

ClawHub 页面：[学稿 · xuegao](https://clawhub.ai/green1515/skills/xuegao)。在运行 OpenClaw 的终端执行，将 `YOUR_AGENT` 替换成目标 agent ID：

```sh
openclaw skills install @green1515/xuegao --agent YOUR_AGENT
openclaw skills list --agent YOUR_AGENT --json
```

也可以使用 ClawHub CLI 安装到当前工作区：

```sh
clawhub install @green1515/xuegao
```

从 GitHub 仓库本地安装时，在 Gateway 能够读取仓库的环境执行：

```sh
openclaw skills install ./skills/xuegao --agent YOUR_AGENT --as xuegao
openclaw skills list --agent YOUR_AGENT --json
```

新会话说：`使用学稿（xuegao），学习上传的稿件并直接成稿。`

确认目标agent实际发现并读取了skill。旧名安装迁移时，将旧`creator-calibration`目录备份到技能发现目录之外，避免同一任务被两份旧新流程同时匹配。不要删除作者资料或用新包覆盖整个账号工作区。见[官方文档](https://docs.openclaw.ai/tools/skills)。

## 自动学习和更新如何落地

skill负责指挥当前模型分析和写作；`scripts/learn.py`负责文稿提取、原文证据校验、版本化状态和风格文件同步。Python 3.9+，仅标准库，不内置额外LLM服务。

agent有读取、执行和写入权限时，可在学习任务中自行完成这些步骤。已有应用数据库则由应用完成同样的调用，不要求用户自己操作命令。详见[内部学习流程](skills/xuegao/references/learning.md)与[应用接入约定](skills/xuegao/references/profile-contract.md)。

在外部Word里改稿却没有回传时，skill无法看见变化；应用需要接入上传或编辑保存事件。本仓库提供事件处理能力，没有假装任何产品的监听器已经上线。无写权限时可先完成本轮创作，但必须说明跨会话保存尚未完成。

新稿生成需同时提供当前风格与本次独立事实包。历史文稿只提供写法，不能拿旧事实、旧数字填补新素材。

## 测试

```sh
python3 -m unittest discover -s tests -v
```

测试覆盖自动学习状态、Word提取、去重、来源证据、人工改稿差异、旧规则替换、账号与版本边界、SOUL区块同步。

模型端到端测试：

```sh
python3 evals/run_learning.py --base-url http://127.0.0.1:18789 \
  --agent YOUR_TEST_AGENT --workdir evals/private/new-run \
  --output evals/private/new-run-result.json
```

先在独立测试agent安装学稿，并通过环境变量`OPENCLAW_TOKEN`提供网关凭据。脚本使用完全合成的Word和文本；解析、存储与同步由测试适配器执行，语义学习和写稿调用已有模型，可能消耗额度。不是自动在真实客户环境创建账号或接入编辑器。

[0.2.0测试记录](evals/XUEGAO-RESULTS.md) · [0.1.0历史记录](evals/RESULTS.md)

公开包不包含客户原稿、私有状态或凭据。GitHub 仓库采用 MIT License；ClawHub 发布版本依照平台要求，同时按 MIT-0 授权，可免费使用、修改和分发且无需署名。
