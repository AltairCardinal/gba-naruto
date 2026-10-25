#!/bin/bash
# U2: build the battle-14 route generator and run it twice.
set -eu
SRC=/mnt/d/Github/gba-naruto/tools/s49_battle_balance/u2_route_gen.cpp
INC=/mnt/d/Shell/Github/gba-naruto-butano/butano-sequel/game/include
OUT=/mnt/d/Github/gba-naruto/build/s49-battle-balance/u2
mkdir -p "$OUT"
g++ -std=c++23 -O1 -w -I "$INC" "$SRC" -o "$OUT/u2_route_gen"
echo "built $OUT/u2_route_gen"
"$OUT/u2_route_gen" --dump > "$OUT/dump.txt"
"$OUT/u2_route_gen" > "$OUT/routeA.json" 2> "$OUT/routeA.err"
echo "run A exit=$?"
"$OUT/u2_route_gen" > "$OUT/routeB.json" 2> "$OUT/routeB.err"
echo "run B exit=$?"
sha256sum "$OUT/routeA.json" "$OUT/routeB.json"
grep -E 'after the battle|after the settlement|ERR ' "$OUT/routeA.err" | tail -5
