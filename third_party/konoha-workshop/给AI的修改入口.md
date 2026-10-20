# 木叶工房后续改造入口

请先阅读00_先看这里.txt、LICENSE、素材与许可说明.txt及源码/重建说明.txt。

编辑器入口是editor/index.html；core.js为解析与导出，features.js/feature_ui.js为地图物品与事件，campaign_editor.js/campaign_ui.js为新战斗，asset_imports.js/asset_ui.js为分类导入，music.js/music_ui.js为原版音乐试听与设置。

DEMO编剧原稿位于源码/continuation/project；扩展程序位于源码/continuation/source，重点是runtime.c、runtime_continuation.c、runtime.S和escape_rules.c。构建器在源码/continuation/tools/build_campaign.js。第二关为人物3抵达(3,11)并结束行动，敌方位置设置不可战胜。

本包没有ROM。需要自行准备完全匹配的原版，先生成基底，再构建。不要向别人索要或传播本人的存档、即时状态或参考音色。

用户提出功能修改后，在独立副本中完成实现与测试。区分编辑器保存/导出通过、原生判定定点检查、模拟器正常按键以及完整通关；未测不能称通过。地图图片、通行属性和撤离判定位置分别配置，任务文字也应同步。

现有剧情与数值是功能演示，不是完善成品。可自由改造；原作者原则上不再继续更新。
