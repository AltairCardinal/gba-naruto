// 场景号（剧情场景 id）的语义 —— **界面各处都要用这一套，别各写各的**。
//
// ## 场景号不是「第几场」
//
// 场景号是**剧情调度器 `0x0808F544` 的入参 r0**，也是四张剧情脚本根表的
// **直接下标**（槽号 = 场景号）：
//
// | 根表 | 文件偏移 | ROM 地址 |
// |---|---|---|
// | before | `0x060C74` | `0x08560C74` |
// | after | `0x060D54` | `0x08560D54` |
// | logic | `0x060E34` | `0x08560E34` |
// | events | `0x060EF0` | `0x08560EF0` |
//
// 依据：
//   * `0x0808F8DC` 用 `ldrb r0, [r4, #0x16]` 取场景号，交给 `0x0808F544`；
//   * L4 逐场留证 **55/55**：游戏实际用的脚本指针与 `before_root[scene]`
//     **逐位相等**（`notes/evidence/l4-playthrough-20261021.md` §1.1 / §4.1）。
//
// ## 场景号的数值大小**不代表剧情顺序**
//
// | 场景号 | 是什么 |
// |---|---|
// | 0 | 空槽（四张根表都没指针） |
// | **1..46** | **关卡场景** —— 场景号 = 关卡号 = 战斗组号 |
// | 47..55 | 关卡之外的特殊场景（见下） |
//
// 特殊场景逐条都有出处：
//
// | 场景号 | 类别 | 依据 |
// |---|---|---|
// | 47 | 短对白 | 战前「走吧！ＭＡＰ０１的家伙。」/ 战后「成功啦～！」 |
// | 48 / 49 | 占位 | 正文「无法进入此处」 |
// | 50 | 主线分支总线 | 开头 13 条 `0x15` 比较器跳转（进度 ==360/261/260、>=250/240/230/110/100/90/89/70/45/0） |
// | 51 | 进度分支 | 开头 5 条 `0x15` 比较器跳转（进度 >=225/172/169/159/150） |
// | 52 | 章节场景 | 「这就是考场吗……」 |
// | 53 | 章节过场 | `0x1E` 进战斗 + 「终于到了！！」 |
// | **54** | **主线入口（游戏开局）** | 开机 → 标题 → START 后走的就是它：调度器命中时 r0 = 0x36 = 54，VM 拿到的脚本指针逐位等于 `before_root[54]` = `0x08049E76` |
// | 55 | 占位 | 正文「此处无法进入。」 |
//
// **所以「游戏开局」在场景号 54，不在场景 1** —— 场景 1 是第 1 关的战前剧情。
// 场景 54 的开头是 5 条 `0x15` 比较器跳转（进度 ==270 / >=229 / >=80 / >=69 / >=27），
// 剧情进度 < 27 时落到开局的过场（鸣人毕业 / 一乐拉面）。
//
// 界面据此把两件事分开说：**场景号是键**（ROM 里的下标，改它 = 改指针），
// **「第几场」是作者心里的顺序**（两者不是一回事）。

/** 关卡场景的场景号范围（场景号 = 关卡号 = 战斗组号）。 */
export const LEVEL_SCENE_MIN = 1;
export const LEVEL_SCENE_MAX = 46;

/** 主线入口：游戏开机（标题 → START）后走的就是这一场。 */
export const ENTRY_SCENE = 54;

/** 占位场景：正文是「此处无法进入。」，游戏里走不到。 */
export const PLACEHOLDER_SCENE = 55;

/** 场景号 → 类别。键是场景号，值是类别与说法。 */
const SPECIAL_SCENES = {
  47: {
    kind: 'short',
    tag: '短对白',
    hint: '战前「走吧！ＭＡＰ０１的家伙。」/ 战后「成功啦～！」—— 教学提示。',
  },
  48: { kind: 'placeholder', tag: '占位', hint: '正文是「无法进入此处」。' },
  49: { kind: 'placeholder', tag: '占位', hint: '正文是「无法进入此处」。' },
  50: {
    kind: 'hub',
    tag: '主线分支',
    hint: '开头 13 条 0x15 比较器跳转：按剧情进度（state[0x10]）选主线分支。' +
      '绝大多数关卡剧情演完都汇到这一场。',
  },
  51: {
    kind: 'hub',
    tag: '进度分支',
    hint: '开头 5 条 0x15 比较器跳转：按剧情进度（state[0x10]）选分支。',
  },
  52: { kind: 'chapter', tag: '章节场景', hint: '「这就是考场吗……」—— 考试篇的过场。' },
  53: { kind: 'chapter', tag: '章节过场', hint: '0x1E 进战斗 + 「终于到了！！」。' },
  54: {
    kind: 'entry',
    tag: '主线入口（游戏开局）',
    hint: '开机 → 标题 → START 后走的就是这一场：剧情调度器命中时 r0 = 0x36 = 54，' +
      'VM 拿到的脚本指针逐位等于 before_root[54] = 0x08049E76。' +
      '开头 5 条 0x15 比较器跳转（进度 ==270 / >=229 / >=80 / >=69 / >=27），' +
      '剧情进度 < 27 时落到开局的过场（鸣人毕业 / 一乐拉面）。',
  },
  55: { kind: 'placeholder', tag: '占位', hint: '正文是「此处无法进入。」，游戏里走不到。' },
};

/** 类别 → 一句话说明（用于没有逐条特例的场景号）。 */
const KIND_HINTS = {
  empty: '这一格在四张根表里都没有指针。',
  level: '场景号 = 关卡号 = 战斗组号。',
};

/**
 * 这一场是哪一类。
 *
 * @param {number} scene 场景号
 * @returns {'level'|'short'|'placeholder'|'hub'|'chapter'|'entry'|'empty'}
 */
export function sceneKind(scene) {
  const n = Number(scene);
  const special = SPECIAL_SCENES[n];
  if (special) return special.kind;
  if (n >= LEVEL_SCENE_MIN && n <= LEVEL_SCENE_MAX) return 'level';
  if (n === 0) return 'empty';
  return 'level';
}

/** 这一场的短标签（关卡场景是「第 N 关」，其余是类别名）。 */
export function sceneTag(scene) {
  const n = Number(scene);
  const special = SPECIAL_SCENES[n];
  if (special) return special.tag;
  if (n >= LEVEL_SCENE_MIN && n <= LEVEL_SCENE_MAX) return `第 ${n} 关`;
  return '场景';
}

/** 这一场的一句话说明（作者看得懂的那种）。 */
export function sceneHint(scene) {
  const n = Number(scene);
  const special = SPECIAL_SCENES[n];
  if (special) return special.hint;
  return KIND_HINTS[sceneKind(n)] || '';
}

/**
 * 这一场的完整标签：**场景号 + 它是什么**。
 *
 * 关卡场景：`场景 12（第 12 关）`
 * 特殊场景：`场景 54 · 主线入口（游戏开局）`
 */
export function sceneLabel(scene) {
  const n = Number(scene);
  const kind = sceneKind(n);
  if (kind === 'level') return `场景 ${n}（第 ${n} 关）`;
  return `场景 ${n} · ${sceneTag(n)}`;
}

/** 只说场景号（标题栏、面包屑这类地方用）。 */
export function sceneName(scene) {
  return `场景 ${Number(scene)}`;
}

/**
 * 一句总的说明：界面上解释「场景号」到底是什么。
 *
 * 这是用户最容易踩的地方 —— 把场景号当成「第几场」，于是**游戏开局
 * （场景 54）看起来像是最后一场**，占位场景（55）还排在它前面。
 */
export const SCENE_ID_NOTE =
  '场景号是 ROM 里的**键**：剧情调度器 0x0808F544 拿它当下标，' +
  '四张剧本根表也按它索引（槽号 = 场景号）。' +
  '**它不是「第几场」** —— 数值大小不代表剧情顺序：' +
  '1..46 是关卡场景（场景号 = 关卡号 = 战斗组号），47..55 是关卡之外的特殊场景，' +
  '其中**游戏开局是场景 54（主线入口）**，55 是占位（「此处无法进入。」）。';

/**
 * 把场景号按「作者找得到」的顺序分组，给下拉用。
 *
 * 主线入口排在最前 —— 它是玩家在游戏里**最先**看到的那一场；
 * 其次是 1..46 的关卡场景；最后是其余特殊场景。
 * **组内仍按场景号升序** —— 场景号是键，顺序不能乱。
 *
 * @param {number[]} scenes 这一根表里可用的场景号
 * @returns {{label: string, scenes: number[]}[]}
 */
export function sceneGroups(scenes) {
  const list = (scenes || []).map(Number);
  const groups = [
    { label: '主线入口（游戏从这里开始）', scenes: [] },
    { label: `关卡场景（第 ${LEVEL_SCENE_MIN}..${LEVEL_SCENE_MAX} 关）`, scenes: [] },
    { label: '其他特殊场景', scenes: [] },
  ];
  for (const scene of list) {
    if (scene === ENTRY_SCENE) groups[0].scenes.push(scene);
    else if (scene >= LEVEL_SCENE_MIN && scene <= LEVEL_SCENE_MAX) groups[1].scenes.push(scene);
    else groups[2].scenes.push(scene);
  }
  return groups.filter((group) => group.scenes.length);
}

/**
 * 一张根表里可用的场景号。
 *
 * 槽 0 在四张根表里都是空的（没有剧本），所以从 1 开始。
 *
 * @param {object} structure 内容包里的根表结构
 * @returns {number[]}
 */
export function sceneNumbers(structure) {
  const records = (structure && structure.records) || [];
  const out = [];
  for (let i = 1; i < records.length; i++) out.push(i);
  return out;
}

/**
 * 场景下拉的分组：**主线入口 → 关卡场景 → 其它特殊场景**。
 *
 * **当前场景不在表内时补一组** —— 例如从「战前剧情」切到「战场事件逻辑」，
 * 而当前场景是 54（那张根表只有 46 个槽）：不补的话下拉会显示第一项，
 * 与页面正在显示的那一场对不上。
 *
 * @param {object} structure 内容包里的根表结构
 * @param {number} current 当前场景号
 * @returns {{label: string, scenes: number[]}[]}
 */
export function sceneOptionGroups(structure, current) {
  const scenes = sceneNumbers(structure);
  const groups = sceneGroups(scenes);
  const n = Number(current);
  if (Number.isFinite(n) && n > 0 && !scenes.includes(n)) {
    groups.push({ label: '当前场景（这张根表里没有这一槽）', scenes: [n] });
  }
  return groups;
}
