#!/bin/bash
# U2: run the battle-14 route generator twice and compare the two key
# scripts byte for byte (the offline controller is deterministic).
set -e
/tmp/u2_route_gen > /tmp/u2_routeA.json 2>/tmp/u2_routeA.err
echo "exitA=$?"
/tmp/u2_route_gen > /tmp/u2_routeB.json 2>/tmp/u2_routeB.err
echo "exitB=$?"
sha256sum /tmp/u2_routeA.json /tmp/u2_routeB.json
head -6 /tmp/u2_routeA.json
grep -c '"key"' /tmp/u2_routeA.json
