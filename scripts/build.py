"""Generate a static, auditable dataset from a pinned F1DB release."""
import json, urllib.request, zipfile, io, pathlib, itertools, collections
VERSION="v2026.21.0"
URL=f"https://github.com/f1db/f1db/releases/download/{VERSION}/f1db-json-single.zip"
def build(data):
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
                # Historical private entrants cannot be reliably distinguished by constructor.
                if race["year"]<1982 or len(rows)!=2: continue
                a,b=rows
                if a["driverId"]==b["driverId"]: continue
                events.append([race["year"],race["round"],race["grandPrixId"],kind,team,a["driverId"],b["driverId"],a["positionNumber"],b["positionNumber"],a.get("reasonRetired"),b.get("reasonRetired")])
    return {"version":VERSION,"drivers":drivers,"teams":teams,"events":events,"coverageStart":1982}
if __name__=="__main__":
    with urllib.request.urlopen(URL,timeout=120) as r: archive=zipfile.ZipFile(io.BytesIO(r.read()))
    names=[n for n in archive.namelist() if n.endswith(".json") and not n.endswith("schema.json")]
    if len(names)!=1: raise ValueError(names)
    out=build(json.loads(archive.read(names[0])))
    assert len(out["events"])>1000, "Incomplete import"
    pathlib.Path("site/data.json").write_text(json.dumps(out,separators=(",",":")),encoding="utf-8")
    print(len(out["events"]),"comparisons")
