# Project Memory Rules

This repository is used as the persistent project memory for the ROM reverse-engineering and sequel-planning work.

Required rules:

1. All meaningful findings must be written into files inside this repository.
2. All effective development work must leave durable project artifacts in this repository.
3. Do not rely on chat history as the primary memory. If something matters later, record it in `notes/`, `docs/`, `tools/`, or another appropriate project file.
4. When a debugging method proves useful, document both the method and the result.
5. When a reverse-engineering conclusion changes, update the relevant note instead of leaving the old state only in conversation.
6. When roadmap progress changes, update `docs/sequel-roadmap.md` in the same work cycle.
7. **防循环守则**（2026-10-23 补；事故复盘见 `notes/evidence/session-loop-analysis-20261023.md`）：
   - **一次尝试必须能回答一个是/否问题。**「还是卡」不是结果，是噪音 ——
     换成能判定的观测（某处补丁开/关能不能跑、屏幕 diff 差在哪一行、某条断言过不过），
     或者换个方向。
   - **一次只改一处，跑一次，记一行。**结论落进**假设台账**
     （一行一个假设：判定方法 / 结果 / 状态 = 未验·已证伪·已确认），
     不要只写叙述性的「我试了 X 不行」—— 下一个会话读台账才能直接接着干。
   - **连续 3 次同样结果 ⇒ 停。**把「这条路走不通」写进台账，换方法，
     不要在同一处试第 4 次。
   - **陷住了就换方法/换会话，不要靠 Goal 续跑硬扛** ——
     续跑提示会逐字重复，只会把同一个状态再喂一遍。
   - 自检：`python tools/loop_guard.py <会话的 messages.jsonl>` ——
     命中就是「真的在打转」，不要继续往下想。

Preferred locations:

- `notes/`: investigation logs, intermediate findings, memory maps, experiment results
- `docs/`: stable plans, workflows, architecture, reverse-engineering strategy
- `tools/`: scripts, automation, reproducible probes

Minimum expectation for each successful step:

- record what was attempted
- record what was learned
- record what file or address range is now important
