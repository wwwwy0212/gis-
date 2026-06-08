---
name: arcgis-pyt-guard
description: ArcGIS 10.x Python Toolbox (.pyt) 制作全流程避坑与合规检查。在编写或修改任何 ArcGIS .pyt 工具箱代码之前，使用此技能进行合规性检查、风险识别和字段生命周期验证。同时适用于：制作面重叠处理、空间分析、要素编辑等 ArcGIS Python Toolbox 工具，或用户提到 ArcGIS、arcpy、工具箱、.pyt、面重叠、去重叠、拓扑修复、ArcMap 工具开发等关键词。Use this skill BEFORE writing any ArcGIS .pyt code, including simple edits.
---

# ArcGIS 10.x .pyt 工具箱制作守护

## 何时使用

满足以下任一条件时，立即调用此技能：
- 用户要求新建或修改 `.pyt` 工具箱文件
- 用户提到 ArcGIS 工具开发、arcpy 工具箱、ArcMap Python Toolbox
- 用户请求面重叠处理、拓扑清理等涉及 arcpy 几何操作的功能
- 用户说"做一个 ArcGIS 工具"或类似表述

## 执行流程

### 第一步：加载避坑参考文档

**在开始编码前**，务必先读取 `references/pitfalls.md`。该文档包含从真实项目中提炼的五大核心坑点和完整检查清单。

### 第二步：合规性检查（编码前）

对照参考文档第四节的检查清单，逐项评估用户需求。如果发现任何未覆盖的边界情况，主动向用户提问。

特别强调以下最容易出错的三项：

1. **目标 ArcGIS 版本**：如果是 10.x，所有中文字符串必须用 `\uXXXX` 转义。
2. **属性保留方案**：如果涉及 Dissolve/Merge/Append 操作，提前设计字段生命周期，选择 statistics_fields 或 JoinField 方案。
3. **辅助字段管理**：列出所有新增字段，确认清理时机。

### 第三步：风险提示

根据用户的工具需求，对照参考文档的五大坑点，指出可能踩中的陷阱：

| 风险点 | 涉及的操作 |
|--------|-----------|
| 坑点 1 - ASCII 编码 | 所有 10.x .pyt 文件 |
| 坑点 2 - Dissolve 丢属性 | Dissolve_management, 合并碎片 |
| 坑点 3 - Intersect 字段改名 | Intersect_analysis, 多源合并 |
| 坑点 4 - 字段生命周期 | Append, Merge, JoinField, _drop_non_output_fields |
| 坑点 5 - 消息兼容性 | messages 对象 API |

### 第四步：编码

在完成以上检查后，开始编写代码。编码时注意：
- 遵循参考文档 3.1 节的标准算法步骤（如适用）
- 使用 `_msg`/`_warn`/`_err` 包装函数而非直接调 arcpy 消息 API
- 编写至少 3 个静态测试（ASCII 编码、参数定义、关键算法特征）

### 第五步：编码后验证

代码完成后，对照参考文档第四节的检查清单做终验，并运行所有测试。
