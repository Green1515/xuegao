# 偏好记录与注入约定

本文件是建议的数据约定，不代表目标应用已经实现这些字段或API。优先适配已有数据库与授权机制，不新建重复的记忆系统。

## 可选本地工具

`scripts/profile.py` 仅使用Python标准库，无联网调用。由已授权的操作者提供可信账号与文件位置；脚本的账号检查不能代替操作系统或应用权限隔离。

```sh
python3 scripts/profile.py --profile .creator-calibration/demo.json --account demo init
python3 scripts/profile.py --profile .creator-calibration/demo.json --account demo record \
  --expected-revision 0 --key opening --value '直接进入主题，不加招呼' \
  --scope 口播 --evidence '作者明确要求：以后不要加招呼' --confirmed
python3 scripts/profile.py --profile .creator-calibration/demo.json --account demo context --scope 口播
```

命令在skill目录执行；其他目录使用脚本绝对路径。默认`record`只新增候选；仅明确用户指令或确认可使用`--confirmed`。替换已确认同key同scope规则时，传入`--replaces`及旧规则ID；不能静默覆盖。每次写入要求`--expected-revision`，防止旧请求覆盖新状态。新会话重新执行`context`得到最新版本，不依赖聊天记忆。

旧版本保存在`<profile>.history/`。该工具不自动恢复历史版本，避免静默撤销后来确认的规则；需要恢复时读取历史，基于当前版本显式记录并替换。进程异常留下`.lock`时先确认无写入任务，人工处理锁文件。不要把本地偏好文件和history提交到公共仓库。

每条偏好至少记录：账号绑定、版本、适用体裁、规则内容、来源、状态、确认时间，以及替代哪一条旧规则。来源应定位到用户消息、人工修改差异或样稿段落。

状态区分：

- `observed`：样稿中观察到，可能是单次写法。
- `proposed`：模型根据反馈推导，尚未得到确认。
- `confirmed`：用户明确提出或确认，范围清楚。
- `superseded`：被后续要求替代，不进入有效规则。

显式“以后不要叫姐妹们”可以直接作为确认偏好；用户接受某一稿，不代表确认所有由模型归纳出的规则。用户说“学习这篇”只授权分析，不代表“模型新写的版本已经验收”。

应用给每次生成提供精简的上下文包：

```json
{
  "account_id": "由应用认证确定",
  "profile_version": "当前生效版本",
  "task": {"format": "观点口播", "duration_seconds": 50},
  "confirmed_preferences": [],
  "relevant_examples": [],
  "current_feedback": [],
  "fact_materials": [],
  "unresolved_conflicts": []
}
```

各列表应包含实际内容和出处，空列表不能被解释成资料已经齐全。样稿只用于表达参考，事实包需要另有来源、日期、地区、对象和核验状态。

日志可记录版本、样稿ID、实际注入的规则ID、写作入口和处理耗时，用于排查“明明学过为什么没用上”。原始正文和用户身份资料按现有访问与留存规则处理，不因本skill另行扩大采集范围。

优先按账号过滤，再在该账号内部按体裁、目的、作者确认和时效选择代表样稿。不要只按主题语义相似检索，也不要只按点赞量选择，以免冷门但有代表性的写法被排除。
