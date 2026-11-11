# Creator Calibration · 创作者校准

An evidence-based Agent Skill for learning an author's writing habits, producing a trial draft, interpreting feedback, and maintaining confirmed preferences. 中文写作与口播为当前主要验证范围。

**目标：让“学过账号”变成“本轮确实按账号要求写”，并减少重复纠正。**

适用：新作者冷启动、新闻素材转原创口播、“不像我”的改稿反馈、账号规则冲突。它不生成虚构亲历，不把样稿事实当新稿事实，也不承诺播放量、涨粉或与真人完全一致。

## 工作方式

1. 从少量同体裁样稿提炼有出处的表达习惯，区分观察和用户确认。
2. 将本次观点、证据、作者立场与长度要求对齐，再生成稿件。
3. 识别反馈属于选题、逻辑、叙述视角、措辞、时长还是事实。
4. 通过已有应用存储或可选本地工具更新有效偏好，替换冲突旧规则。
5. 在新会话和不同入口验证实际使用的版本。

安装skill不会自动改造产品数据库或统一已有接口。应用集成仍需将相同的账号偏好与相关样稿提供给各入口。详见[接入约定](skills/creator-calibration/references/profile-contract.md)。

## 安装

```sh
git clone https://github.com/Green1515/creator-calibration.git
cd creator-calibration
```

以下命令默认目标目录不存在；已有同名skill时先比较版本，不直接覆盖。

### Codex

个人安装：

```sh
mkdir -p ~/.agents/skills
test ! -e ~/.agents/skills/creator-calibration && cp -R skills/creator-calibration ~/.agents/skills/
```

在新会话输入：`使用 $creator-calibration，根据我的样稿和修改意见写一条口播。`

项目安装可复制到项目的`.agents/skills/creator-calibration/`。若当前会话未显示新skill，重新开始会话。路径依据[官方文档](https://learn.chatgpt.com/docs/build-skills)。

### Claude Code

```sh
mkdir -p ~/.claude/skills
test ! -e ~/.claude/skills/creator-calibration && cp -R skills/creator-calibration ~/.claude/skills/
```

输入：`/creator-calibration 根据这些样稿和修改意见写口播。`

项目安装可复制到`.claude/skills/creator-calibration/`。这只是本地Claude Code安装，不等于上传到claude.ai或云会话。见[官方说明](https://code.claude.com/docs/en/skills)。

### OpenClaw

在运行Gateway且能读取仓库的环境中执行：

```sh
openclaw skills install ./skills/creator-calibration --agent YOUR_TEST_AGENT --as creator-calibration
openclaw skills list --agent YOUR_TEST_AGENT --json
```

也可把skill文件夹复制到目标agent工作区的`skills/creator-calibration/`。确认其catalog包含`creator-calibration`，再在新会话明确要求使用它。不要只安装在main目录就假定其他agent也可见。见[官方文档](https://docs.openclaw.ai/tools/skills)。

**兼容范围不等于实测范围。** 本仓库会在[测试结果](evals/RESULTS.md)分别说明真实运行、格式校验和仅文档核对的状态。

## 使用示例

```text
使用creator-calibration。
这里是我的两条观点口播样稿：……
我确认的偏好：直接进入主题，不加招呼；不要“这篇文章认为”的评稿口吻。
当前事实材料：……
本次任务：面向本地居民，写一条约40秒的口播，主张是……，结尾互动。
先给正文。事实缺口和估时单独说明，不要编造本人经历。
```

没有样稿也可开始，但只能建立暂定方向，不能声称已经学会作者风格。用户明确说“学习这篇”不等于确认模型推导出的全部永久规则。

## 可选偏好存储

Python 3.9+，仅标准库，无API或额外依赖。在skill目录运行：

```sh
python3 scripts/profile.py --profile .creator-calibration/demo.json --account demo init
python3 scripts/profile.py --profile .creator-calibration/demo.json --account demo record \
  --expected-revision 0 --key opening --value '直接进入主题，不加招呼' \
  --scope 口播 --evidence '作者明确要求以后不加招呼' --confirmed
python3 scripts/profile.py --profile .creator-calibration/demo.json --account demo context --scope 口播
```

本地工具保护账号绑定、版本一致性、候选与已确认状态、显式替换和历史快照；不代替应用授权和文件权限隔离。已有产品数据库时优先复用。

## 验证

```sh
python3 -m unittest discover -s tests -v
```

`evals/cases.json`含完全合成的测试素材，`evals/run_openclaw.py`用独立测试agent比较基线和skill。它从环境变量`OPENCLAW_TOKEN`读取凭据，不把凭据写入结果。

```sh
python3 evals/run_openclaw.py --base-url http://127.0.0.1:18789 \
  --baseline-agent YOUR_BASELINE_AGENT --candidate-agent YOUR_SKILL_AGENT \
  --output evals/private/local-run.json
```

这会调用你配置的模型，可能消耗已有额度。测试前准备两个只含合成资料的独立agent，为candidate安装skill；两者使用同一个模型。测试脚本不自动创建账号，不自动发布内容。客观检查不代替真实编辑验收；字数不是实际朗读时长。

本项目仅发布通用方法与合成素材，不包含客户账号、历史聊天、原始客户文稿、服务器地址或认证信息。MIT License。
