# Fyuu Tutor

[English](README.md) · 当前版本：**v0.1.0 Preview**

把可信材料变成一套 AI Tutor 能长期接着教的课程。

Fyuu Tutor 是一个面向 Codex、以材料和学习证据为基础的自适应教学 Skill。你可以交给它一个概念、教材、题库或学习目标，它会建立并持续运行三种学习路径之一：

- **能力学习**：理解、应用、构建、决策和迁移。
- **认证考试**：把考纲映射到课程、题目和备考成熟度。
- **语言学习**：在真实场景中理解和主动表达目标语言。

它不是一次性课件生成器。课程覆盖、学习证据、薄弱点和下一步都会保存在独立的私人项目中，让不同 Agent 能按相同标准继续教学。

## 三项核心能力

### 1. 从材料到课程

先诊断 PDF 等输入，选择可靠且成本最低的提取方式，进行独立校验，再把全部必学内容映射到课程、练习和参考资料。

### 2. 三条学习管线

| 管线 | 适用结果 |
|---|---|
| Capability | 能独立解释、决策、构建、应用或迁移一种能力 |
| Certification | 覆盖有版本和日期的考纲，并能在考试条件下作答 |
| Language | 能在真实场景中理解或产出目标语言 |

管线由成功证据决定，而不是由输入格式决定。同一份 PDF 可以服务于不同的学习路径。

### 3. 自适应教学闭环

系统把学习状态分为 **Produced、Studied、Demonstrated、Stable**。它会记录错误类型、寻找最早的阻塞点、生成最小但有效的下一课，并在延迟或变化场景下重新检查薄弱项。

## 安装

确定性脚本需要 Python 3.11 或以上版本。

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo fyuuwang/fyuu-tutor \
  --path fyuu-tutor
```

PDF 工具可以按需使用 MarkItDown、RapidOCR、PyMuPDF 或 Poppler，但这些依赖不是必需项，也不会自动安装。

## 使用示例

```text
使用 $fyuu-tutor，把这些系统设计概念建立成能力学习项目，并根据我的实际回答安排下一课。

使用 $fyuu-tutor，把这份考纲和题库整理成认证备考课程，并建立可追溯的覆盖映射。

使用 $fyuu-tutor，根据这些对话材料建立英语口语项目，在主动表达通过前不要推进。
```

也可以确定性地创建一个空项目：

```bash
python3 fyuu-tutor/scripts/create_project.py \
  --root ./private-learning/projects \
  --project-id english-speaking \
  --display-name "英语口语" \
  --pipeline language \
  --content-language zh-CN
```

教材、用户画像、课程成品、学习证据和实时状态始终放在公开仓库之外。

## 工作流程

1. 登记并校验可信材料或学习目标。
2. 建立带来源锚点的知识地图和课程覆盖矩阵。
3. 路由到一种主要学习管线。
4. 生成 HTML 课程、练习和紧凑参考资料。
5. 记录证据和错误，再选择下一步。

## 来源与 Fyuu Tutor 的增量

Fyuu Tutor 派生自 Matt Pocock 的 [`teach`](https://github.com/mattpocock/skills/tree/main/skills/productivity/teach) Skill，并依据 MIT 许可证保留和改造了持续教学工作区、Mission、HTML 课程、学习记录、最近发展区、检索练习、间隔学习和反馈循环等思想。

在此基础上，Fyuu Tutor 增加了：

- 能力、认证和语言三管线路由；
- 材料诊断、OCR 多重校验、规范化和覆盖映射；
- 四级学习证据和错误干预路由；
- 认证考纲、权威材料版本和考试日期控制；
- 带版本的私人项目协议和多 Agent 认领机制；
- 隐私、链接、项目结构和输出校验程序。

Bloom、Universal Diagnostic Tutor、AI Tutor Skill、Education Agent Skills、Mr. Ranedeer AI Tutor 和 Tutor GPT 仅用于产品研究，没有复制其代码或提示词。完整许可证与边界见 [THIRD_PARTY_NOTICES.md](fyuu-tutor/THIRD_PARTY_NOTICES.md)。

## 版本和许可证

`v0.1.0` 是公开预览版。预览阶段的破坏性变化必须附带迁移说明；从 `v1.0.0` 开始严格遵循语义化版本兼容规则。

参见 [CHANGELOG.md](CHANGELOG.md)、[CONTRIBUTING.md](CONTRIBUTING.md)、[SECURITY.md](SECURITY.md) 和 [MIT LICENSE](LICENSE)。
