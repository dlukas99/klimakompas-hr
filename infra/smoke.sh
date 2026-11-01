#!/usr/bin/env bash
# Smoke test after a deploy (SPEC §17). Usage: infra/smoke.sh https://demo.example
set -uo pipefail
BASE="${1:?give the base URL}"
failed=0

check() {
  local name="$1" url="$2" expect="$3"
  local body
  if body=$(curl -fsS --max-time 30 "$url") && grep -q "$expect" <<<"$body"; then
    echo "OK    $name"
  else
    echo "FAIL  $name"
    failed=1
  fi
}

check "health" "$BASE/api/v1/health" '"ok"'
check "ready" "$BASE/api/v1/ready" '"ready"'
check "iskaznica Osijek" "$BASE/api/v1/card?lat=45.555&lon=18.69" '"hazards"'
check "iskaznica Split" "$BASE/api/v1/card?lat=43.51&lon=16.44" '"hazards"'
check "iskaznica Zagreb" "$BASE/api/v1/card?lat=45.81&lon=15.97" '"hazards"'
check "geokoder" "$BASE/api/v1/geocode?q=Osijek" '"Osijek"'
check "JLS" "$BASE/api/v1/jls/03123" '"Osijek"'
check "izvori" "$BASE/api/v1/sources" '"dgu_au"'
check "brzo pitanje" "$BASE/api/v1/agent/quick?question=warnings" '"text"'
check "web" "$BASE/karta" 'KlimaKompas'
check "podaci" "$BASE/podaci" 'KlimaKompas'
check "OGC" "$BASE/ogc/collections?f=json" 'grid_risk'
check "DCAT" "$BASE/api/v1/catalog.ttl" 'dcat:Dataset'
if curl -fsS --max-time 30 -o /dev/null "$BASE/tiles/jls_risk/8/138/90"; then
  echo "OK    pločice"
else
  echo "FAIL  pločice"
  failed=1
fi
exit "$failed"
