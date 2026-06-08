# ArcGIS 10.x Python Toolbox (.pyt) 制作全流程与避坑要点

> 本文档基于"面重叠处理工具"从 v1.0 到 v1.2 的完整开发过程提炼。
> 每次制作 ArcGIS 10.x .pyt 工具箱前，按本清单逐项检查。

---

## 一、项目结构规范

### 1.1 最小可交付文件

```
项目根目录/
├── 工具箱名.pyt          ← 唯一必需文件，可在 ArcMap 中直接加载
├── .gitignore            ← git 仓库必备
├── tests/                ← 静态测试（不依赖 arcpy 运行时）
│   └── test_*.py
└── README.md             ← 功能说明、使用方法、兼容性表格
```

### 1.2 .pyt 文件内部结构模板

```
class Toolbox(object):           ← 工具箱容器
    def __init__(self):          ← label, alias, tools 列表
    class ToolName(object):      ← 具体工具
        def __init__(self):      ← label, description, canRunInBackground
        def getParameterInfo(self):  ← 输入输出参数定义
        def isLicensed(self):
        def updateParameters(self):
        def updateMessages(self):    ← 参数校验（如数据类型检查）
        def execute(self, parameters, messages):  ← 核心逻辑
```

### 1.3 .gitignore 必要条目

```gitignore
# Python
__pycache__/
*.pyc
*.pyo

# ArcGIS generated（自动生成的 .tbx 和 .xml 不入库）
*.tbx
*.xml

# Temp
*.tmp
temp/

# IDE
.vscode/
.idea/

# System
Thumbs.db
.DS_Store
```

---

## 二、五大核心避坑要点（按严重程度排序）

### 坑点 1：ASCII 编码 —— ArcGIS 10.x 会拒绝加载含非 ASCII 字符的 .pyt

**现象：** .pyt 文件在 ArcMap 工具箱中显示"已损坏"或无法识别。

**根因：** ArcGIS 10.x 在某些 Windows 代码页下，若 .pyt 文件包含原始的中文字符（非 ASCII 字节），Python 解释器会报告文件损坏。

**解决方案：** 所有字符串中的中文字符必须用 `\uXXXX` Unicode 转义序列。

```python
# ❌ 错误 —— 直接写中文
arcpy.AddMessage("流程：自相交提取 -> 擦除合并输出")
arcpy.AddError("输入图层不存在或不可访问。")

# ✅ 正确 —— 使用 Unicode 转义
arcpy.AddMessage(u"流程：自相交提取 -> "
                 u"擦除合并输出")
arcpy.AddError(u"输入图层不存在或不可访问。")
```

**检查方法：** 新增测试 `test_toolbox_source_is_ascii_only_for_arcgis_10_loader`：
```python
def test_toolbox_source_is_ascii_only_for_arcgis_10_loader(self):
    PYT.read_bytes().decode("ascii")  # 如果抛出 UnicodeDecodeError 就说明有漏网之鱼
```

**实用技巧：** 用 Python 在线工具批量转换中文字符串为 `\uXXXX` 格式，避免手动编写。
```python
# 转换工具：输入中文，输出 \uXXXX 字符串
print(repr(u"你的中文").lstrip("u"))
```

> ⚠️ **踩坑记录：** v1.2 开发过程中，修改中文流程描述时直接写了汉字而非转义，导致 .pyt 在 ArcGIS 10.6 中加载失败。

---

### 坑点 2：Dissolve 操作丢失属性 —— 输出只剩 OBJECTID/Shape/Shape_Length/Shape_Area

**现象：** 工具运行成功，但输出属性表只有 `OBJECTID`、`Shape`、`Shape_Length`、`Shape_Area` 四个字段，所有用户属性（如 DLMC、MJ、QSXZ 等）全部丢失。

**根因链条：**

ArcGIS `Dissolve_management` 的 `statistics_fields` 参数机制有三个陷阱：

1. **不传 statistics_fields → 只保留 dissolve key + 计数**：所有非 key 字段被丢弃。
2. **传了 → 输出字段自动加前缀**：`["DLMC", "FIRST"]` 在输出中变成 `FIRST_DLMC`。如果后续用 `_drop_non_output_fields(dissolved_fc, original_fields)` 清理字段，`original_fields` 里的 `DLMC` 匹配不到 `FIRST_DLMC`，字段被全部删除。
3. **`AlterField_management` 改名有字段名长度限制**：GDB 字段名最多 64 字符，`FIRST_` 前缀可能导致超长截断。

**推荐方案 —— 用 JoinField 回填属性**（本工具最终采用的方案）：

```python
# Step 1: Dissolve 不做属性统计，只做几何合并
arcpy.Dissolve_management(merge_fc, dissolved_fc, "MERGE_KEY", "", "MULTI_PART")

# Step 2: 从 src_a 准备属性表
join_table = os.path.join(gdb_path, "src_attr")
arcpy.CopyFeatures_management(src_a, join_table)
arcpy.AddField_management(join_table, "MERGE_KEY", "LONG")
arcpy.CalculateField_management(join_table, "MERGE_KEY", "!A_ORIGOID!", "PYTHON_9.3")

# Step 3: 用 JoinField 把属性回填到溶解结果
arcpy.JoinField_management(dissolved_fc, "MERGE_KEY", join_table, "MERGE_KEY", original_fields)

# Step 4: 最后再清理辅助字段
_drop_non_output_fields(dissolved_fc, original_fields)
```

**关键顺序：** Dissolve → JoinField → _drop_non_output_fields。不能在 JoinField 之前清理 MERGE_KEY，否则 join 失败。

> ⚠️ **踩坑记录：** v1.1 和 v1.2 两次踩了同一个坑。第一次用 `statistics_fields` 传 `"FIRST"` 导致输出字段变成 `FIRST_*`；第二次改用 JoinField 方案但 `_drop_non_output_fields` 在 JoinField 之前调用了，MERGE_KEY 被删导致 join 静默失败。

---

### 坑点 3：Intersect_analysis 字段重命名 —— 同名字段加数字后缀

**现象：** 调用 `arcpy.Intersect_analysis([src_a, src_b], raw_fc, "ALL", "", "INPUT")` 后，`raw_fc` 中来自 `src_b` 的用户属性字段自动添加数字后缀（如 `DLMC` → `DLMC_1`）。

**影响：**
1. 后续用 `Append_management(overlap_fc, merge_fc, "NO_TEST")` 时，`overlap_fc` 的字段名与 `merge_fc`（来自 erased）不一致，用户属性值可能写入错误的列。
2. 如果 `NO_TEST` 模式静默丢弃不匹配的字段，overlap 行的用户属性全变成 NULL。

**解决方案：**
- 在 overlap 数据进入 merge 步骤之前，用 `_drop_non_output_fields` 删除所有非用户字段和辅助字段，只保留与 `erased_fc` 完全一致的字段集。
- 使用 `KEEP_SIDE = 'A'` 时，overlap 行的用户属性来自 src_a（字段名未被 Intersect 修改），与 erased 的字段名天然一致。
- 关键原则：**merge 的两个源必须在字段名和字段集上完全一致，否则 Append 会出问题**。

> ⚠️ **踩坑记录：** v1.1 为了实现 Dissolve 方案，去掉了一个关键的 `_drop_non_output_fields(overlap_sorted, original_fields)` 调用。这导致 overlap 数据带着 `FID_src_a`, `FID_src_b`, `B_ORIGOID`, `DLMC_1` 等杂字段进入 merge，Append 时 schema 不匹配。

---

### 坑点 4：辅助字段的生命周期管理 —— 增删时机错了就断链

**现象：** 执行到某个步骤时报错"字段不存在"或结果中残留临时字段。

**涉及字段：**
| 字段名 | 来源 | 作用 | 何时不再需要 |
|--------|------|------|-------------|
| `A_ORIGOID` | `_capture_original_order(src_a)` | 追踪 erased 碎片归属 | Dissolve 完成后 |
| `B_ORIGOID` | `_capture_original_order(src_b)` | Intersect 中用于计算 KEEP_OID | Step 2/3 结束后 |
| `KEEP_OID` | `min(ao, bo)` 计算 | 追踪 overlap 归属 | Dissolve 完成后 |
| `KEEP_SIDE` | `"A"` or `"B"` | 筛选去重 | Step 2/3 删除相同项后 |
| `IS_OVLP` | 自相交分类 | 筛选跨图斑重叠 | Step 2/3 结束后 |
| `MERGE_KEY` | `A_ORIGOID` 或 `KEEP_OID` | Dissolve 分组键 | Dissolve 完成后 |

**管理原则：**
1. **只在一处做最终清理**：在 Dissolve 之后的 `dissolved_fc` 上调用一次 `_drop_non_output_fields`，确保中间步骤需要的字段不被提前删除。
2. **在创建 MERGE_KEY 时，源字段必须还在**：`A_ORIGOID` 和 `KEEP_OID` 不能在添加 `MERGE_KEY` 之前被清理。
3. **`_field_names_to_keep` 的 helper_fields 列表必须完整**：每新增一个辅助字段，必须同步更新此列表，否则字段漏删导致输出脏数据。

```python
# helper_fields 集中管理
helper_fields = ["A_ORIGOID", "B_ORIGOID", "IS_OVLP", "KEEP_OID", "KEEP_SIDE", "MERGE_KEY"]
```

> ⚠️ **踩坑记录：** 新增 MERGE_KEY 字段时忘记加入 helper_fields 列表，导致 `_drop_non_output_fields` 未能删除 MERGE_KEY，输出结果中残留了临时字段。

---

### 坑点 5：消息系统兼容性 —— 不同 ArcGIS 版本 API 差异

**现象：** 在 ArcGIS 10.x 不同小版本中，`messages` 对象的 API 不一致（有的用 `addMessage`，有的用 `AddMessage`）。

**解决方案：** 封装消息辅助函数，对多种 API 名称做 fallback：

```python
def _send_gp_message(messages, text, level):
    """兼容不同 ArcGIS 版本的 messages API"""
    method_map = {
        "message": ["addMessage", "AddMessage"],
        "warning": ["addWarning", "AddWarning"],
        "error":   ["addError",   "AddError"],
    }
    for method_name in method_map.get(level, []):
        method = getattr(messages, method_name, None)
        if method:
            method(text)
            return
    # 最后兜底：全局 arcpy.AddMessage/AddWarning/AddError
    getattr(arcpy, "Add" + level.capitalize())(text)
```

**原则：** 工具代码中只使用 `_msg(messages, text)`、`_warn(messages, text)`、`_err(messages, text)`，永远不直接调 `messages.AddMessage`。

> ⚠️ **踩坑记录：** 编写之初没有充分测试 10.3/10.6 版本差异，但好在设计时做了兼容 fallback。

---

## 三、单图层面重叠处理标准算法

### 3.1 算法步骤（已验证可用）

```
输入：单个面要素类
输出：无空间重叠的面要素类（每个输出要素 = 一个原始图斑的所有碎片合并）

Step 0: 复制输入两份（src_a, src_b），各自记录原始 OID
Step 1: 自相交提取（Intersect_analysis[src_a, src_b], "ALL"）
       ↓
       分类：IS_OVLP = (FID_src_a != FID_src_b)
       KEEP_OID = min(A_ORIGOID, B_ORIGOID)
       KEEP_SIDE = 'A' when A_ORIGOID <= B_ORIGOID
Step 2: 去重（Select IS_OVLP=1 AND KEEP_SIDE='A' → Sort by KEEP_OID → DeleteIdentical on Shape）
Step 3: 擦除（Erase_analysis src_a by overlap）→ 非重叠碎片
       ↓
       合并：erased（A_ORIGOID→MERGE_KEY）+ overlap（KEEP_OID→MERGE_KEY）
       ↓
       Dissolve by MERGE_KEY (MULTI_PART)
       ↓
       JoinField 回填属性 from src_a on MERGE_KEY
       ↓
       清理辅助字段 → 输出
```

### 3.2 边界情况

| 场景 | 处理 |
|------|------|
| 输入无重叠 | `raw_count == 0` 或 `overlap_count == 0` → 直接 CopyFeatures 返回 |
| 输入为空 | `input_count == 0` → 报错提示 |
| 几何破损 | `CheckGeometry_management` 先行检查，有破损则报错并要求先修复 |
| 输出路径被锁 | `_write_final_output` 的 fallback 机制，使用 `OverlapResult_<uid>` 安全名称 |
| 临时数据清理 | `finally` 块中删除整个临时 GDB，无论成功或异常 |

---

## 四、编码前的检查清单（按流程排列）

在开始编写代码前，逐项确认：

### 环境兼容性
- [ ] 目标 ArcGIS 版本是多少？（10.3 / 10.6 / Pro）
- [ ] 如果目标是 10.x：确认 .pyt 文件需要 ASCII-only 编码
- [ ] 确认 arcpy 版本对应的 Python 版本（10.x 用 Python 2.7）

### .pyt 文件规范
- [ ] 所有中文字符串已转为 `\uXXXX` 转义（或确认目标版本支持 UTF-8）
- [ ] 有 ASCII 编码测试
- [ ] 消息系统使用包装函数（`_msg`/`_warn`/`_err`），不直接调 `messages.AddMessage`
- [ ] Toolbox 的 label 和 alias 明确有意义
- [ ] 工具 description 用简洁中文说明功能

### 参数设计
- [ ] `getParameterInfo` 只暴露必要参数（输入、输出），不暴露内部配置
- [ ] 输入参数有 `filter.list` 限制数据类型
- [ ] `updateMessages` 做输入参数验证

### 算法设计
- [ ] 明确每一步输入什么、输出什么
- [ ] 画出数据流图，标注每个字段的生命周期
- [ ] 确认 Dissolve/Merge/Append 等会改变字段结构的关键操作

### 字段管理（最易出错）
- [ ] 列出所有辅助字段及其生命周期
- [ ] `helper_fields` 列表是否完整
- [ ] `_drop_non_output_fields` 调用时机是否正确（只在最后，不在中间）
- [ ] Append 的两个源字段集是否一致（如不一致，确认 NO_TEST 行为）

### 属性保留
- [ ] 任何属性字段被删除的操作都有替代方案（或不发生）
- [ ] Dissolve 的方案选择：statistics_fields 还是 JoinField
- [ ] 验证：输出属性表应与输入属性表字段一致

### 错误处理
- [ ] 输入不存在、输入为空、输入非面图层 → 有明确中文错误提示
- [ ] 几何破损 → 有检查 + 提示
- [ ] 输出路径异常 → 有 fallback
- [ ] finally 块清理临时数据

### 测试
- [ ] 有 ASCII 编码测试
- [ ] 有参数数量测试
- [ ] 有关键算法特征测试（如 KEEP_OID / Dissolve / MERGE_KEY）
- [ ] 有输出写入 fallback 测试
- [ ] 有消息系统测试
