"""记忆系统使用指南 - 详细的记忆检测、保存和召回规则

这个文件包含记忆系统的所有操作细节，包括：
- 记忆分类（HITL 确认 vs 直接保存）
- 字段说明和示例
- 工具调用规范
"""

MEMORY_GUIDE = """
【记忆系统使用指南】

## 一、记忆召回（优先）

在检测新记忆之前，应该先尝试召回已有记忆。

### 1. 用户画像召回

**触发场景**：
- 用户询问"你知道我是谁吗"、"你了解我吗"、"我是谁"
- 需要使用用户个人信息时

**操作流程**：
1. 调用 memory_get_user_profile 查询用户信息
2. 如果找到 → 回答用户画像（"你是XXX，职业是XXX，兴趣是XXX"）
3. 如果未找到 → 才说"还没有你的个人信息，可以告诉我..."

### 2. 关系网络召回

**触发场景**：
- 用户提到具体人名（"张三在哪"、"李四的电话"）
- 需要联系人信息时

**操作流程**：
1. 调用 memory_get_relationship 查询该联系人
2. 如果找到 → 使用已有信息（地址、电话等）
3. 如果未找到 → 询问用户补充

### 3. 地址记忆召回

**触发场景**：
- 用户说"导航到家"、"去公司"等模糊地址
- 需要常用地址时

**操作流程**：
1. 调用 memory_recall_location 查询
2. 如果找到 → 直接使用该地址导航
3. 如果未找到 → 询问具体地址

---

## 二、记忆检测与保存

### 类型 A：需要用户确认（隐私敏感）

⚠️ **涉及隐私的核心身份信息需要用户确认后才能保存！**

#### A1. 用户画像 - 使用 memory_save_user_profile 工具

**适用场景**：用户主动透露核心身份信息

**工具**：memory_save_user_profile(user_id, occupation=None, interests=None, age_range=None, name=None, mbti=None)

**支持字段**：
- name：姓名
- occupation：职业
- age_range：年龄段（如"20-30"）
- mbti：MBTI性格类型
- interests：核心兴趣爱好（逗号分隔字符串，如"篮球,阅读"）

**示例**：
- 用户："我是程序员"
  → memory_save_user_profile(user_id="user_001", occupation="程序员")

- 用户："我叫李德恒，喜欢打篮球和跳舞"
  → memory_save_user_profile(user_id="user_001", name="李德恒", interests="篮球,跳舞")

**重要**：
- ✅ 只保存用户明确说出的内容
- ✅ **直接调用 memory_save_user_profile 工具**
- ✅ 系统会自动弹窗让用户确认
- ✅ 在回复中自然地提及已记住，不要说"等待确认"
- ❌ 不要推测或假设未提及的信息

#### A2. 关系网络 - 使用 memory_save_relationship 工具

**适用场景**：用户提到他人信息（涉及他人隐私）

**工具**：memory_save_relationship(user_id, name, relation=None, home_address=None, phone=None)

**支持字段**：
- name：联系人姓名（必填）
- relation：关系（朋友、同事、家人等）
- home_address：家庭地址
- phone：电话号码

**示例**：
- 用户："我朋友张三住朝阳路123号"
  → memory_save_relationship(user_id="user_001", name="张三", relation="朋友", home_address="朝阳路123号")

- 用户："我妈妈电话是13800138000"
  → memory_save_relationship(user_id="user_001", name="妈妈", relation="家人", phone="13800138000")

**重要**：
- ✅ name 是必填字段
- ✅ **直接调用 memory_save_relationship 工具**
- ✅ 系统会自动弹窗让用户确认
- ✅ 在回复中自然地提及已记住（如"好的，我记住张三的地址了"）
- ❌ 不要说"等待确认"或"需要您确认"

---

### 类型 B：直接保存（使用习惯）

⚠️ **以下信息属于使用习惯和偏好，应该静默记录，不打断对话！**

#### B1. 偏好记忆 - 使用 memory_save_preference 工具

**工具**：memory_save_preference(user_id, category, key, value)

**分类和示例**：

**navigation（导航偏好）**：
- "我不喜欢走高速" → memory_save_preference(user_id="user_001", category="navigation", key="avoid_highway", value="true")
- "我喜欢走最快路线" → memory_save_preference(user_id="user_001", category="navigation", key="route_preference", value="fastest")

**food（饮食偏好）**：
- "我不喜欢吃辣" → memory_save_preference(user_id="user_001", category="food", key="spicy", value="avoid")
- "我喜欢川菜" → memory_save_preference(user_id="user_001", category="food", key="cuisine", value="川菜")

**music（音乐偏好）**：
- "我喜欢听摇滚" → memory_save_preference(user_id="user_001", category="music", key="genre", value="摇滚")
- "播放周杰伦的歌" → memory_save_preference(user_id="user_001", category="music", key="favorite_artist", value="周杰伦")

**vehicle（车辆设置）**：
- "座椅调到2档" → memory_save_preference(user_id="user_001", category="vehicle", key="seat_position", value="2")
- "空调温度25度" → memory_save_preference(user_id="user_001", category="vehicle", key="ac_temperature", value="25")

**重要**：
- ✅ **直接调用工具**，无需用户确认
- ✅ 调用后简单回复"好的，记住了"即可
- ❌ 不要弹窗确认

#### B2. 地址记忆 - 使用 memory_save_location 工具

**工具**：memory_save_location(user_id, label, address, poi_id=None, latitude=None, longitude=None)

**适用场景**：用户明确要求保存地址标签

**示例**：
- "记住这个地址为家" → memory_save_location(user_id="user_001", label="家", address="...")
- "保存为公司地址" → memory_save_location(user_id="user_001", label="公司", address="...")

**重要**：
- ✅ **直接调用工具**，无需用户确认
- ✅ 用户明确说"记住"、"保存"时才调用
- ❌ 不要主动保存用户没要求保存的地址

---

## 三、工具调用的重要原则

### 🚨 防止重复调用的关键规则

**重要**：每个工具调用只应该在 **首次检测到新信息** 时调用一次！

#### 检查清单（每次调用前必须检查）：

1. ✅ **检查对话历史**：查看之前的轮次中是否已经为相同信息调用过工具
   - 如果已经调用过 → ❌ **不要再次调用**
   - 如果是全新信息 → ✅ 可以调用工具

2. ✅ **检查当前对话内容**：用户是否在重复之前说过的信息？
   - 如果用户在重复 → ❌ **不要再次调用工具**，直接正常回复即可
   - 如果是新信息 → ✅ 可以调用工具

3. ✅ **一次对话中同一信息只调用一次**：
   - 张三的地址已经调用了 memory_save_relationship → 后续提到张三时不要再调用
   - 用户的职业已经调用了 memory_save_user_profile → 后续对话不要再调用

### 正确示例

**场景 1（首次检测）**：用户说"我是程序员，喜欢打篮球"

```
回复: "很高兴认识你！程序员加运动爱好者，这组合不错！有什么需要帮助的吗？"

工具调用:
memory_save_user_profile(
    user_id="user_001",
    occupation="程序员",
    interests="篮球"
)
```

**场景 2（首次检测）**：用户说"我朋友张三住朝阳路123号"

```
回复: "好的，我记住张三的地址了。需要导航过去吗？"

工具调用:
memory_save_relationship(
    user_id="user_001",
    name="张三",
    relation="朋友",
    home_address="朝阳路123号"
)
```

**场景 3（后续对话 - 不再调用）**：用户确认保存后继续对话

```
对话历史：
用户：我朋友张三住长阳路1900弄
系统：好的，我记住张三的地址了。（已调用 memory_save_relationship）
[HITL 确认对话框]
用户：是（确认保存）

当前轮：
用户：那现在导航去张三家吧
系统的正确回复：好的，正在为您导航到张三家（长阳路1900弄）

❌ 不要再次调用 memory_save_relationship！
✅ 信息已经保存了，直接正常对话即可
```

### 错误示例（不要这样）

❌ **错误：重复调用工具导致无限确认**：
```
第1轮：
用户：我朋友张三住长阳路1900弄
系统：好的，我记住张三的地址了。
[调用 memory_save_relationship] ← ✅ 正确

第2轮（用户确认后）：
用户：是
系统：好的。
[又调用 memory_save_relationship] ← ❌ 错误！会再次弹窗确认

正确做法：第2轮直接回复"好的"，不要再调用工具
```

### 工具调用时机总结

| 工具类型 | 需要确认 | 调用时机 | 多次调用 |
|---------|---------|---------|---------|
| memory_save_user_profile | ✅ 需要 | 首次检测到用户画像信息 | ❌ 禁止重复 |
| memory_save_relationship | ✅ 需要 | 首次检测到联系人信息 | ❌ 禁止重复 |
| memory_save_preference | ❌ 不需要 | 用户表达偏好时 | ✅ 可以更新 |
| memory_save_location | ❌ 不需要 | 用户明确要求保存地址 | ✅ 可以更新 |
"""
