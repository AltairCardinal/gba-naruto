import { ref } from 'vue'

type Locale = 'zh' | 'ja' | 'en'

const currentLocale = ref<Locale>('zh')

const translations = {
  zh: {
    appTitle: '木叶战记续作 - 编辑器',
    dialogues: '对话管理',
    battleConfigs: '战斗配置',
    units: '单位配置',
    skills: '技能配置',
    storyBeats: '剧情节拍',
    audio: '音频管理',
    build: '构建',
    map: '地图编辑',
    users: '用户管理',
    create: '新建',
    edit: '编辑',
    delete: '删除',
    save: '保存',
    cancel: '取消',
    confirm: '确认',
    name: '名称',
    type: '类型',
    hp: 'HP',
    attack: '攻击',
    defense: '防御',
    speed: '速度',
    team: '队伍',
    chapter: '章节',
    scenario: '场景',
    turnLimit: '回合限制',
    winCondition: '胜利条件',
    loseCondition: '失败条件',
    playerUnits: '我方单位',
    enemyUnits: '敌方单位',
    damage: '伤害',
    heal: '回复',
    range: '范围',
    cost: '消耗',
    effectType: '效果类型',
    description: '描述',
    triggerType: '触发类型',
    triggerParam: '触发参数',
    dialogueKey: '对话Key',
    battleConfigId: '战斗配置ID',
    mapId: '地图ID',
    position: '位置',
    nextBeat: '下一节拍',
    beatIndex: '索引',
    beatType: '类型',
    title: '标题',
    index: 'ID',
    role: '角色',
    username: '用户名',
    password: '密码',
    createdAt: '创建时间',
    actions: '操作',
    noData: '暂无数据',
    required: '必填',
    optional: '可选'
  },
  ja: {
    appTitle: '木葉戦記続作 - エディター',
    dialogues: '-dialogogue-',
    battleConfigs: '-battle-config-',
    units: '-unit-',
    skills: '-skill-',
    storyBeats: '-story-beat-',
    audio: '-audio-',
    build: '-build-',
    map: '-map-',
    users: '-user-',
    create: '新規作成',
    edit: '編集',
    delete: '削除',
    save: '保存',
    cancel: 'キャンセル',
    confirm: '確認',
    name: '名前',
    type: 'タイプ',
    hp: 'HP',
    attack: '攻撃',
    defense: '防御',
    speed: '速度',
    team: 'チーム',
    chapter: 'チャプター',
    scenario: 'シナリオ',
    turnLimit: 'ターン制限',
    winCondition: '勝利条件',
    loseCondition: '敗北条件',
    playerUnits: '味方のユニット',
    enemyUnits: '敵のユニット',
    damage: 'ダメージ',
    heal: '回復',
    range: '範囲',
    cost: 'コスト',
    effectType: '効果タイプ',
    description: '説明',
    triggerType: 'トリガータイプ',
    triggerParam: 'トリガー引数',
    dialogueKey: '対話キー',
    battleConfigId: '戦闘設定ID',
    mapId: 'マップID',
    position: '位置',
    nextBeat: '次のビート',
    beatIndex: 'インデックス',
    beatType: 'タイプ',
    title: 'タイトル',
    index: 'ID',
    role: '役割',
    username: 'ユーザー名',
    password: 'パスワード',
    createdAt: '作成日時',
    actions: '操作',
    noData: 'データなし',
    required: '必須',
    optional: '任意'
  }
}

export function t(key: string): string {
  return translations[currentLocale.value]?.[key as keyof typeof translations['zh']] || key
}

export function setLocale(locale: Locale) {
  currentLocale.value = locale
}

export function getLocale(): Locale {
  return currentLocale.value
}

export const useI18n = () => ({
  t,
  setLocale,
  locale: currentLocale
})
