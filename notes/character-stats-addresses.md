# Character Stats (人物数据) Addresses

**来源：** 第三方逆向成果（图片提取）  
**WRAM 地址范围：** `0x02022EF0` - `0x02022FDF`（每角色 0x50 字节）

---

## 角色 1 数据块（首地址：`0x02022EF0`）

| 地址偏移 | 名称 | 说明 |
|----------|------|------|
| +0x00 `02022EF0` | 人物(1) ID | 角色 ID |
| +0x01 `02022EF1` | 等级 | Level |
| +0x02 `02022EF2` | 攻击力 | Attack Power |
| +0x03 `02022EF3` | 防御力 | Defense Power |
| +0x04 `02022EF4` | 敏捷度 | Agility |
| +0x05 `02022EF5` | 移动力 | Movement |
| +0x06 `02022EF6` | 忍具数 | Ninja Tool Count |
| +0x07 `02022EF7` | （空） | |
| +0x08 `02022EF8` | 查克拉 | Chakra |
| +0x09 `02022EF9` | （空） | |
| +0x0A `02022EFA` | 与印数值相同，未知 | 与手印数相同，功用不明（红色） |
| +0x0B `02022EFB` | （空） | |
| +0x0C `02022EFC` | 与体力值数值相同，未知 | 与HP相同，功用不明（红色） |
| +0x0D `02022EFD` | （空） | |
| +0x0E `02022EFE` | 与体力值数值相同，未知 | 与HP相同，功用不明（红色） |
| +0x0F `02022EFF` | （空） | |
| +0x10 `02022F00` | 经验值（低字节） | Experience Points |
| +0x11 `02022F01` | 经验值（高字节） | |
| +0x12-0x13 `02022F02-02022F03` | （空） | |
| +0x14 `02022F04` | 主动技能(1) ID | Active Skill 1 ID |
| +0x15 `02022F05` | 该技能等级 | Skill 1 Level |
| +0x16-0x17 `02022F06-02022F07` | （空值） | |
| +0x18 `02022F08` | 主动技能(2) ID | Active Skill 2 ID |
| +0x19 `02022F09` | 该技能等级 | Skill 2 Level |
| +0x1A-0x1B `02022F0A-02022F0B` | （空） | |
| +0x1C `02022F0C` | 主动技能(3) ID | Active Skill 3 ID |
| +0x1D `02022F0D` | 该技能等级 | Skill 3 Level |
| +0x1E-0x1F `02022F0E-02022F0F` | （空） | |
| +0x20 `02022F10` | 主动技能(4) ID | Active Skill 4 ID |
| +0x21 `02022F11` | 该技能等级 | Skill 4 Level |
| +0x22-0x23 `02022F12-02022F13` | （空） | |
| +0x24 `02022F14` | 技能(5) ID | Skill 5 ID |
| +0x25 `02022F15` | 该技能等级 | Skill 5 Level |
| +0x26-0x27 `02022F16-02022F17` | （空） | |
| +0x28 `02022F18` | 技能(6) ID | Skill 6 ID |
| +0x29 `02022F19` | 该技能等级 | Skill 6 Level |
| +0x2A-0x2B `02022F1A-02022F1B` | （空） | |
| +0x2C `02022F1C` | 技能(7) ID | Skill 7 ID |
| +0x2D `02022F1D` | 该技能等级 | Skill 7 Level |
| +0x2E-0x3F `02022F1E-02022F3F` | （空） | |
| +0x40 `02022F40` | 被动技能 ID | Passive Skill ID |
| +0x41 `02022F41` | 该技能等级 | Passive Skill Level |
| +0x42-0x9B `02022F42-02022F9B` | （空） | |
| +0x9C `02022F9C` | 被动技能 ID | Passive Skill ID（第二个被动技能？） |
| +0x9D `02022F9D` | 该技能等级 | Passive Skill Level |
| +0x9E-0x9F `02022F9E-02022F9F` | （空值） | |
| +0xA0 `02022FA0` | 未知 | |
| +0xA1 `02022FA1` | 未知 | |
| +0xA2 `02022FA2` | 未知 | |
| +0xA3 `02022FA3` | 未知 | |
| +0xA4 `02022FA4` | 未知 | |
| +0xA5 `02022FA5` | 未知 | |
| +0xA6 `02022FA6` | 未知 | |
| +0xA7 `02022FA7` | 未知 | |
| +0xA8 `02022FA8` | 未知 | |
| +0xA9 `02022FA9` | 未知 | |
| +0xAA `02022FAA` | 剩余修炼点 | Remaining Training Points |
| +0xAB `02022FAB` | 未知 | |

**角色 1 数据块结构（共 0x50 = 80 字节）：** `0x02022EF0` - `0x02022F3F`

---

## 角色 2 数据块（首地址：`0x02022FAC`）

| 地址偏移 | 名称 | 说明 |
|----------|------|------|
| +0x00 `02022FAC` | 人物(2) ID | Character 2 ID |
| +0x01 `02022FAD` | 等级 | Level |
| +0x02 `02022FAE` | 攻击力 | Attack Power |
| +0x03 `02022FAF` | 防御力 | Defense Power |
| +0x04 `02022FB0` | 敏捷度 | Agility |
| +0x05 `02022FB1` | 移动力 | Movement |
| +0x06 `02022FB2` | 忍具数 | Ninja Tool Count |
| +0x07 `02022FB3` | （空） | |
| +0x08 `02022FB4` | 查克拉 | Chakra |
| +0x09 `02022FB5` | （空） | |
| +0x0A `02022FB6` | 与印数值相同，未知 | 与手印数相同（红色） |
| +0x0B `02022FB7` | （空） | |
| +0x0C `02022FB8` | 与体力值数值相同，未知 | 与HP相同（红色） |
| +0x0D `02022FB9` | （空） | |
| +0x0E `02022FBA` | 与体力值数值相同，未知 | 与HP相同（红色） |
| +0x0F `02022FBB` | （空） | |
| +0x10 `02022FBC` | 经验值（低字节） | Experience Points |
| +0x11 `02022FBD` | 经验值（高字节） | |
| +0x12-0x13 `02022FBE-02022FBF` | （空） | |
| +0x14 `02022FC0` | 技能(1) ID | Skill 1 ID |
| +0x15 `02022FC1` | 该技能等级 | Skill 1 Level |
| +0x16-0x17 `02022FC2-02022FC3` | （空） | |
| +0x18 `02022FC4` | 技能(1) ID | Skill 2 ID（同上结构） |
| +0x19 `02022FC5` | 该技能等级 | Skill 2 Level |
| +0x1A-0x1B `02022FC6-02022FC7` | （空） | |
| +0x1C `02022FC8` | 技能(1) ID | Skill 3 ID |
| +0x1D `02022FC9` | 该技能等级 | Skill 3 Level |
| +0x1E-0x1F `02022FCA-02022FCB` | （空） | |
| +0x20 `02022FCC` | 技能(1) ID | Skill 4 ID |
| +0x21 `02022FCD` | 该技能等级 | Skill 4 Level |
| +0x22-0x2F `02022FCE-02022FDF` | （空） | |

**角色 2 数据块结构（共 0x50 = 80 字节）：** `0x02022FAC` - `0x02022FFB`

---

## 数据结构总结

### 基础属性（每角色 8 字节）

```
0x00: u8   ID
0x01: u8   Level
0x02: u8   Attack
0x03: u8   Defense
0x04: u8   Agility
0x05: u8   Movement
0x06: u8   Ninja Tool Count
0x07: (empty)
0x08: u16  Chakra (LE? 或 u8)
0x0A: u8   [未知，与手印数相同]
0x0C: u8   [未知，与HP相同]
0x0E: u8   [未知，与HP相同]
0x10: u16  Experience Points (LE)
```

### 技能槽（每角色最多 7 个主动 + 1 个被动）

```
技能N ID:    u8
技能N Level: u8
(各占 2 字节，间隔排列)
```

### 被动技能

```
0x40: u8  Passive Skill ID
0x41: u8  Passive Skill Level
0x9C: u8  Passive Skill 2 ID（第二被动？）
0x9D: u8  Passive Skill 2 Level
```

---

## 与现有项目数据的关联

- 与 `notes/unit-skill-addresses.md` 中的 Unit ID 映射表（ROM `0x0853F298`）对应
- 角色 1/2 的 ID 字段应与 Unit ID Mapping Table 中的 index 对应
- `notes/ninja-tool-addresses.md` 中的道具数据地址范围为 `0x02023FD4` 起，独立于此结构
- 可整合到 `tools/import_battle_config.py` 的角色数据 patch 生成逻辑中
