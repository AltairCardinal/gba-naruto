# 逆向推进吞吐量实测

- 采样时间：2026-10-19T15:05:03.572181+00:00
- 主机：12 逻辑核，可用磁盘 9.92 GiB，可用物理内存 6467.0 MiB，1 分钟负载 10.12
- 解释器：/usr/local/bin/python3

## 各阶段实测

| 阶段 | 类型 | 墙钟(s) | 峰值RSS(MiB) | 退出码 | 守卫结论 |
| --- | --- | ---: | ---: | ---: | --- |
| coverage-audit | static | 60.82 | 269.015625 | 124 | idle-timeout |
| unknown-ranking | static | 1.31 | 0.9140625 | 0 | completed |
| formal-proof | heavy | 60.24 | 208.60546875 | 124 | idle-timeout |

## 探针

- CPU 并行：4 工作者，串行 11.707s vs 并行 4.711s，加速 2.485x，并行效率 0.621
- heavy 锁争用：2/2 个并发受管运行被以 lock-busy 拒绝

## 瓶颈排序

### 0. heavy-work-lock-serialization（hard）

- 证据：2/2 concurrent guarded runs were rejected with lock-busy instead of waiting for the project heavy lock
- 影响：at most one guarded heavy operation (mGBA capture, formal proof replay) can run at a time; extra sub-agents cannot add heavy throughput, they only add rejected runs
- 处置：fan out read-only reconnaissance and static analysis; keep every heavy stage on the single guarded path and queue it explicitly

### 2. disk-headroom（soft）

- 证据：only 9.92 GiB available on the data volume
- 影响：artifact regeneration, mGBA capture and formal receipts all write to disk; a full volume fails runs late and wastes the compute spent before the failure
- 处置：reclaim regenerable experiment trees before starting a heavy stage, and keep new captures under one run-id directory

### 4. single-heavy-stage-latency（soft）

- 证据：slowest heavy stage 'formal-proof' took 60.24s
- 影响：a single guarded stage can dominate a milestone's wall clock; policy already forbids repeating a full formal audit for one small packet
- 处置：batch packets up to the policy threshold and use the measured stage cost to decide how many milestones fit in a session

