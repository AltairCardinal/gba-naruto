// main.cpp — 火影忍者：木叶战记 静态重编译移植版 入口
//
// 参照 gbarecomp 框架参考游戏 MinishCapRecomp 的 src/main.cpp 形态。
// 框架提供：窗口 / 音频 / 输入 / 存档 / mod / 回滚联机 / 诊断回放 / 自愈调度。
// 本文件只负责：声明"我是哪个游戏" + 把参数交给 run_game()。
//
// 用法：
//   NarutoKonohaSenkiRecomp [--bios <path>] [--rom <path>] [game.toml]
//
// BIOS 与 ROM 都必须在启动前通过哈希校验，否则运行时拒绝启动：
//   * ROM  = 本仓库 rom/base.gba（熊组简体中文汉化版）
//             SHA-1 26f60795fa5e63b4f0264b84e453beffd56b9f7d
//   * BIOS = 玩家自己主机导出的 gba_bios.bin（16 KB）
//             SHA-1 300c20df6731a33952ded8c436f7f186d25d3492
//
// 无窗口 / 脚本化运行（用于回归测试与覆盖率测量）：
//   NarutoKonohaSenikaRecomp --no-window --frames 600 --rom <path> --bios <path>
//   环境变量 GBARECOMP_NO_LAUNCHER=1 跳过启动器。

#include <cstdio>
#include <cstring>

#include "runtime.h"

namespace {

void print_usage() {
    std::printf(
        "NarutoKonohaSenkiRecomp [--bios <path>] [--rom <path>] [game.toml]\n"
        "\n"
        "BIOS 与 ROM 都必须通过哈希校验（可直接写在 game.toml 的 [bios]/[rom] 段）。\n"
        "默认 BIOS 路径：gbarecomp/bios/gba_bios.bin\n"
        "默认游戏配置：game.toml（当前工作目录）\n");
}

}  // namespace

int main(int argc, char** argv) {
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--help") == 0 || std::strcmp(argv[i], "-h") == 0) {
            print_usage();
            return 0;
        }
    }

    gbarecomp::RunOptions opts;
    opts.builtin_game_name = "Naruto: Konoha Senki";
    // 与本仓库 rom/base.gba 一致（熊组简体中文汉化版）。
    opts.builtin_rom_sha1  = "26f60795fa5e63b4f0264b84e453beffd56b9f7d";
    opts.mod_game_id       = "naruto-konoha-senki-cn";
    opts.launcher_region   = "CN";
    opts.launcher_game_config = "game.toml";
    // 存档：ROM 内无标准 SDK 签名，gba_scan 返回 unknown；
    // 本仓库 rom/base.sav 为 32768 字节 → 判定为 32 KB SRAM
    // （实测声明 EEPROM 会被运行时拒绝：
    //   "save size 32768 is incompatible with EEPROM (expected 512 or 8192)"）。
    opts.launcher_expose_adaptive_view = false;

    return gbarecomp::run_game(argc, argv, opts);
}
