"""Generate a static, auditable dataset from a pinned F1DB release."""
import json, urllib.request, zipfile, io, pathlib, itertools, collections
START_YEAR=2000
VERSION="v2026.21.0"
URL=f"https://github.com/f1db/f1db/releases/download/{VERSION}/f1db-json-single.zip"
def build(data):
    # Retain only a pre-period participation flag, never pre-period results.
    earlier={row["driverId"] for race in data["races"] if race["year"]<START_YEAR for row in (race.get("raceResults") or []) if row.get("laps") or row.get("positionNumber") or row.get("positionText") in ("DNF","NC")}
    races=[r for r in data["races"] if r["year"]>=START_YEAR]
    sessions=("raceResults","qualifyingResults","sprintRaceResults","sprintQualifyingResults")
    driver_ids={row["driverId"] for race in races for field in sessions for row in (race.get(field) or [])}
    team_ids={row["constructorId"] for race in races for field in sessions for row in (race.get(field) or [])}
    data={**data,"races":races,"drivers":[d for d in data["drivers"] if d["id"] in driver_ids],"constructors":[d for d in data["constructors"] if d["id"] in team_ids],"earlierDrivers":earlier}
    drivers={d["id"]:d["name"] for d in data["drivers"]}
    teams={d["id"]:d["name"] for d in data["constructors"]}
    events=[]
    for race in sorted(data["races"],key=lambda r:(r["year"],r["round"])):
        for kind,field in [("race","raceResults"),("qualifying","qualifyingResults"),("sprint","sprintRaceResults"),("sprint qualifying","sprintQualifyingResults")]:
            groups=collections.defaultdict(list)
            for row in race.get(field) or []:
                if row.get("sharedCar") or not row.get("positionNumber"): continue
                groups[row["constructorId"]].append(row)
            for team, rows in groups.items():
                if len(rows)!=2: continue
                a,b=rows
                if a["driverId"]==b["driverId"]: continue
                events.append([race["year"],race["round"],race["grandPrixId"],kind,team,a["driverId"],b["driverId"],a["positionNumber"],b["positionNumber"],a.get("reasonRetired"),b.get("reasonRetired")])
    from analytics import analytics
    return {"version":VERSION,"drivers":drivers,"teams":teams,"events":events,"coverageStart":START_YEAR,"analytics":analytics(data,events)}
if __name__=="__main__":
    with urllib.request.urlopen(URL,timeout=120) as r: archive=zipfile.ZipFile(io.BytesIO(r.read()))
    names=[n for n in archive.namelist() if n.endswith(".json") and not n.endswith("schema.json")]
    if len(names)!=1: raise ValueError(names)
    out=build(json.loads(archive.read(names[0])))
    assert len(out["events"])>1000, "Incomplete import"
    pathlib.Path("site/data.json").write_text(json.dumps(out,separators=(",",":")),encoding="utf-8")
    assert all(e[0]>=START_YEAR for e in out["events"])
    print(len(out["events"]),"comparisons; coverage starts",START_YEAR)
