"""Recorded-result analytics; missing observations are excluded."""
from collections import defaultdict, Counter
from statistics import mean, pstdev
from datetime import date
import re

def analytics(data, events):
    names={d["id"]:d["name"] for d in data["drivers"]}
    teams={d["id"]:d["name"] for d in data["constructors"]}
    circuits={d["id"]:d["name"] for d in data["circuits"]}
    births={d["id"]:d.get("dateOfBirth") for d in data["drivers"]}
    catalog=[]
    def add(section,title,method,columns,rows):
        catalog.append(dict(section=section,title=title,method=method,columns=columns,rows=rows))
    def group(rows,key):
        d=defaultdict(list)
        for r in rows:d[key(r)].append(r)
        return d
    def rank(section,title,method,rows,columns=["Name","Value","Sample"],reverse=True):
        add(section,title,method,columns,sorted(rows,key=lambda r:r[1],reverse=reverse))
    def pos(r):return r.get("positionNumber")
    def grid(r):return r.get("gridPositionNumber")
    def started(r):return r.get("positionText") not in ("DNS","DNQ","DNP","DNPQ","PL") and (bool(r.get("laps")) or bool(grid(r)) or r.get("positionText") in ("DNF","NC"))
    def nm(k):return names.get(k,k)
    def tm(k):return teams.get(k,k)
    def pct(a,b):return round(100*a/b,2) if b else 0
    races=sorted(data["races"],key=lambda r:(r["year"],r["round"]))
    rr=[]; qq=[]; pit=[]; standings=defaultdict(list); completed=[]
    for race in races:
        year=race["year"]; rnd=race["round"]; label=f'{year} · {race["grandPrixId"]}'
        if race.get("raceResults"):completed.append(race)
        for field,dest in [("raceResults",rr),("qualifyingResults",qq),("pitStops",pit)]:
            for x in race.get(field) or []:
                dest.append(dict(x,y=year,round=rnd,event=label,circuit=race["circuitId"],date=race["date"]))
        if race.get("driverStandings") and race.get("raceResults"):standings[year].append(race)
    starts=[r for r in rr if started(r) and not r.get("sharedCar")]
    classified=[r for r in starts if pos(r)]
    by=group(starts,lambda r:r["driverId"]); cl=group(classified,lambda r:r["driverId"])
    ds=group(starts,lambda r:(r["driverId"],r["y"]))
    ts=group(starts,lambda r:(r["constructorId"],r["y"]))
    qevent=group(qq,lambda r:(r["y"],r["round"],r["constructorId"]))
    def qtime(r):return r.get("timeMillis")
    qdiff=defaultdict(list)
    for (y,_,t),a in qevent.items():
        if y<1982 or len(a)!=2:continue
        x,z=a
        # Compare the same qualifying segment, never Q1 against Q3.
        for f in ["q3Millis","q2Millis","q1Millis","timeMillis"]:
            if x.get(f) and z.get(f):
                qdiff[x["driverId"]].append(100*(z[f]-x[f])/z[f])
                qdiff[z["driverId"]].append(100*(x[f]-z[f])/x[f]);break
    rank("Drivers","Qualifying dominance","Mean percentage advantage over the other constructor driver in the latest mutually timed segment, 1982+, minimum 10.",[[nm(k),round(mean(v),3),len(v)] for k,v in qdiff.items() if len(v)>=10],["Driver","Mean advantage %","Pairs"])
    dif=defaultdict(list); h2h=defaultdict(list); partners=defaultdict(set)
    for y,r,g,s,t,a,b,p,q,*_ in events:
        partners[a].add(b);partners[b].add(a)
        for d,x,z in [(a,p,q),(b,q,p)]:
            h2h[d].append((y,s,x,z))
            if s=="race":dif[d].append(z-x)
    rank("Drivers","Race dominance","Mean teammate finishing-position advantage, classified pairs since 1982, minimum 10.",[[nm(k),round(mean(v),2),len(v)] for k,v in dif.items() if len(v)>=10])
    rank("Drivers","Consistency","Population standard deviation of classified finishing positions, minimum 20; lower is more consistent, not necessarily faster.",[[nm(k),round(pstdev([pos(r) for r in v]),2),len(v)] for k,v in cl.items() if len(v)>=20],reverse=False)
    rank("Drivers","Net positions gained","Mean grid minus classified finish; not an overtake count; minimum 20.",[[nm(k),round(mean([grid(r)-pos(r) for r in v if grid(r)]),2),sum(bool(grid(r)) for r in v)] for k,v in cl.items() if sum(bool(grid(r)) for r in v)>=20])
    for title,n,finish in [("Pole conversion",1,1),("Top-three start conversion",3,3)]:
        rows=[]
        for k,v in by.items():
            a=[r for r in v if grid(r) and grid(r)<=n]
            if a:rows.append([nm(k),pct(sum(bool(pos(r) and pos(r)<=finish) for r in a),len(a)),len(a)])
        rank("Drivers",title,"Percentage of starts from qualifying grid threshold resulting in corresponding finish; retirements count as non-conversions.",rows,["Driver","Conversion %","Starts"])
    contrib=[]
    for (t,y),v in ts.items():
        p=Counter()
        for r in v:p[r["driverId"]]+=r.get("points") or 0
        total=sum(p.values())
        if total:contrib.extend([[nm(k)+" · "+tm(t)+" · "+str(y),pct(a,total),round(a,2)] for k,a in p.items()])
    rank("Drivers","Points contribution","Share of recorded Grand Prix driver points by constructor-season; excludes sprint and constructor-specific scoring rules.",contrib,["Driver / team / season","Share %","Race points"])
    first={k:min(r["y"] for r in v) for k,v in by.items()}
    rank("Drivers","Rookie teammate performance","First recorded race-start season, eligible teammate sessions since 1982; minimum 5.",[[nm(k),pct(sum(x<z for y,s,x,z in v if y==first.get(k))+.5*sum(x==z for y,s,x,z in v if y==first.get(k)),sum(y==first.get(k) for y,s,x,z in v)),sum(y==first.get(k) for y,s,x,z in v)] for k,v in h2h.items() if sum(y==first.get(k) for y,s,x,z in v)>=5])
    progression=[]; transfers=[]; streaks=[]; records=[]
    for k,v in by.items():
        seasons=group(v,lambda r:r["y"]);prev=None
        for y,a in sorted(seasons.items()):
            b=[r for r in a if pos(r)]
            age=None
            if births.get(k):
                try:age=round((date.fromisoformat(a[0]["date"])-date.fromisoformat(births[k])).days/365.2425,1)
                except ValueError:pass
            progression.append([nm(k),y,age,len(a),sum(pos(r)==1 for r in a),sum(bool(pos(r) and pos(r)<=3) for r in a),round(sum(r.get("points") or 0 for r in a),2),round(mean(map(pos,b)),2) if b else None])
            teamset={r["constructorId"] for r in a}
            if prev and len(teamset)==len(prev[1])==1 and teamset!=prev[1] and y==prev[0]+1:
                transfers.append([nm(k),y,tm(next(iter(prev[1]))),tm(next(iter(teamset))),prev[2],round(mean(map(pos,b)),2) if b else None])
            prev=(y,teamset,round(mean(map(pos,b)),2) if b else None)
        for title,pred in [("Wins",lambda r:pos(r)==1),("Podiums",lambda r:bool(pos(r) and pos(r)<=3)),("Points finishes",lambda r:(r.get("points") or 0)>0)]:
            best=run=0
            for r in v:run=run+1 if pred(r) else 0;best=max(best,run)
            if best:streaks.append([nm(k),title,best])
        wins=[r for r in v if pos(r)==1];pod=sum(bool(pos(r) and pos(r)<=3) for r in v)
        if wins:records.append([nm(k),"Starts before first win",v.index(wins[0])])
        elif pod:records.append([nm(k),"Podiums without victory",pod])
        if not any(grid(r)==1 for r in v):records.append([nm(k),"Starts without pole grid position",len(v)])
        if partners[k]:records.append([nm(k),"Distinct observed teammates",len(partners[k])])
        if wins and births.get(k):
            for r in wins:
                try:records.append([nm(k),"Age at victory (years)",round((date.fromisoformat(r["date"])-date.fromisoformat(births[k])).days/365.2425,3),r["event"]])
                except ValueError:pass
        run=best=0
        for y,s,x,z in h2h[k]:run=run+1 if x>z else 0;best=max(run,best)
        if best:records.append([nm(k),"Consecutive teammate defeats (recorded sessions)",best])
    add("Drivers","Career progression","Season-by-season Grand Prix starts, wins, podiums, points and classified mean finish. Age at first start of season.",["Driver","Season","Age","Starts","Wins","Podiums","Points","Mean finish"],progression)
    add("Drivers","Team changes","Consecutive seasons with one different constructor each; mean classified finish before and after, not causal attribution.",["Driver","Season","From","To","Prior mean","New mean"],transfers)
    add("Drivers","Career streaks","Consecutive recorded starts satisfying criterion; shared cars excluded.",["Driver","Type","Longest streak"],sorted(streaks,key=lambda x:-x[2]))
    reasons=Counter((nm(r["driverId"]),r["reasonRetired"]) for r in starts if r.get("reasonRetired"))
    add("Drivers","Retirement reasons","Recorded source reasons, no inferred fault or mechanical classification.",["Driver","Recorded reason","Count"],[[a,b,c] for (a,b),c in reasons.most_common()])
    circuitrows=[]
    for (c,k),v in group(starts,lambda r:(r["circuit"],r["driverId"])).items():
        circuitrows.append([circuits.get(c,c),nm(k),len(v),sum(pos(r)==1 for r in v),sum(bool(pos(r) and pos(r)<=3) for r in v)])
    add("Circuits","Driver circuit records","Recorded starts, wins and podiums by circuit (layouts pooled).",["Circuit","Driver","Starts","Wins","Podiums"],circuitrows)
    teamrows=[]; dep=[]; development=[]
    seasoncount=Counter(r["year"] for r in completed)
    for (t,y),v in ts.items():
        ev=group(v,lambda r:r["round"]);wins=sum(any(pos(r)==1 for r in a) for a in ev.values());one2=sum({1,2}.issubset({pos(r) for r in a}) for a in ev.values())
        teamrows.append([tm(t),y,len(ev),wins,pct(wins,seasoncount[y]),one2])
        p=Counter()
        for r in v:p[r["driverId"]]+=r.get("points") or 0
        if sum(p.values()):
            k,n=p.most_common(1)[0];dep.append([tm(t),y,nm(k),pct(n,sum(p.values()))])
        for rnd,a in sorted(ev.items()):
            b=[pos(r) for r in a if pos(r)]
            development.append([tm(t),y,rnd,min(b) if b else None,round(mean(b),2) if b else None])
    add("Constructors","Season dominance and one-twos","Grand Prix wins as share of all completed season races; one-two requires both finishing positions.",["Constructor","Season","Events entered","Wins","Win %","One-twos"],teamrows)
    add("Constructors","Driver dependency","Largest driver share of Grand Prix points, excluding sprint and constructor scoring differences.",["Constructor","Season","Top contributor","Share %"],dep)
    add("Constructors","Development race","Round-by-round best and mean classified finish, not a pure car-speed measure.",["Constructor","Season","Round","Best finish","Mean finish"],development)
    add("Constructors","Regulation transitions","Observed race win shares in consecutive seasons around selected major regulation changes; descriptive only.",["Constructor","Change year","Prior win %","New win %"],[[t,y,next((r[4] for r in teamrows if r[0]==t and r[1]==y-1),None),p] for t,y,_,_,p,_ in teamrows if y in (1989,1994,1998,2009,2014,2017,2022,2026)])
    pr=group([r for r in pit if r.get("timeMillis")],lambda r:(r["constructorId"],r["y"]))
    add("Constructors","Recorded pit-stop times","Source recorded total stop time in seconds, not necessarily stationary wheel-change duration.",["Constructor","Season","Mean seconds","SD seconds","Stops"],[[tm(t),y,round(mean([r["timeMillis"] for r in v])/1000,2),round(pstdev([r["timeMillis"] for r in v])/1000,2),len(v)] for (t,y),v in pr.items()])
    cr=Counter((tm(r["constructorId"]),r["y"],r["reasonRetired"]) for r in starts if r.get("reasonRetired"))
    add("Constructors","Retirement reasons","Recorded reasons and counts; no guessed mechanical classification.",["Constructor","Season","Reason","Count"],[[a,b,c,n] for (a,b,c),n in cr.most_common()])
    qspread=[];qteam=[];margins=[]
    for race in completed:
        y=race["year"];label=f'{y} · {race["grandPrixId"]}'
        a=race.get("qualifyingResults") or []
        # Same segment only, report segment explicitly.
        for f in ["q1Millis","q2Millis","q3Millis","timeMillis"]:
            b=[r for r in a if r.get(f)]
            if len(b)<2:continue
            if f=="timeMillis" and any(r.get("q1Millis") for r in a):continue
            fastest=min(r[f] for r in b);slowest=max(r[f] for r in b)
            qspread.append([label,f,pct(slowest-fastest,fastest),len(b)])
            for t,v in group(b,lambda r:r["constructorId"]).items():qteam.append([tm(t),label,f,round(100*(min(r[f] for r in v)-fastest)/fastest,3)])
        second=next((r for r in race["raceResults"] if pos(r)==2),None)
        winner=next((r for r in race["raceResults"] if pos(r)==1),None)
        if second and winner and second.get("gapMillis") is not None and not second.get("gapLaps"):
            margins.append([label,nm(winner["driverId"]),nm(second["driverId"]),second["gapMillis"]/1000])
        if winner and grid(winner):records.append([nm(winner["driverId"]),"Winning starting position",grid(winner),label])
    add("Championships","Qualifying field spread","Slowest versus fastest timed lap in the same reported segment; percentage.",["Event","Segment","Spread %","Timed drivers"],qspread)
    add("Constructors","Qualifying competitiveness","Best constructor lap deficit to fastest field lap in same segment.",["Constructor","Event","Segment","Deficit %"],qteam)
    add("Championships","Race winning margins","Recorded winner-to-runner-up time gap, excluding lap gaps and missing timing.",["Event","Winner","Runner-up","Seconds"],margins)
    champ=[]; timeline=[]; champions=set()
    for y,v in sorted(standings.items()):
        final=v[-1]["driverStandings"];winner=next((r for r in final if r.get("positionNumber")==1),None);second=next((r for r in final if r.get("positionNumber")==2),None)
        if not winner:continue
        confirmed=any(r.get("championshipWon") for r in final if r["driverId"]==winner["driverId"])
        if confirmed:champions.add(winner["driverId"])
        changes=0;prev=None;deficit=0;clinch=None
        for race in v:
            a=race["driverStandings"];lead=next((r for r in a if r.get("positionNumber")==1),None);w=next((r for r in a if r["driverId"]==winner["driverId"]),None)
            if not lead:continue
            if prev and prev!=lead["driverId"]:changes+=1
            prev=lead["driverId"]
            if w:
                deficit=max(deficit,lead["points"]-w["points"])
                if w.get("championshipWon") and clinch is None:clinch=race["round"]
            timeline.append([y,race["round"],nm(lead["driverId"]),lead["points"]])
        racewinners={r["driverId"] for r in rr if r["y"]==y and pos(r)==1}
        champ.append([y,nm(winner["driverId"]),round(winner["points"]-second["points"],2) if second else None,len(racewinners),changes,round(deficit,2) if confirmed else None,clinch,"Confirmed" if confirmed else "Snapshot leader"])
    add("Championships","Season battles","Official recorded standings: points margins under original rules, distinct GP winners, round-end lead changes, confirmed champion maximum deficit and first recorded title flag. In-progress seasons labeled.",["Season","Leader","Margin pts","Race winners","Lead changes","Deficit overcome","Clinched round","Status"],champ)
    add("Championships","Championship timeline","Recorded leader after each Grand Prix.",["Season","Round","Leader","Points"],timeline)
    for d in data["drivers"]:
        if d.get("totalRaceWins") and d.get("totalChampionshipWins")==0:records.append([d["name"],"Wins without championship",d["totalRaceWins"]])
    add("Records","Unusual records","Recorded career and event statistics; use search for record category and sort value ascending/descending. Shared-car exclusions apply to derived starts.",["Driver","Record","Value","Event"],[r+[None]*(4-len(r)) for r in records])
    # Conservative reason classification: unknown reasons remain unclassified.
    mechanical=re.compile(r"^(engine|gearbox|transmission|clutch|hydraulics|electrical|electronics|brakes|brake|suspension|driveshaft|differential|fuel pump|oil pump|water pump|turbo|radiator|alternator|battery|ignition|power unit|mechanical|steering|exhaust|cooling|oil leak|water leak)$",re.I)
    incident=re.compile(r"^(accident|collision|spun off|spin|crash|damage|collision damage)$",re.I)
    for section,groups,display in [("Drivers",by,lambda k:nm(k)),("Constructors",ts,lambda k:tm(k[0])+" · "+str(k[1]))]:
        rows=[]
        for k,v in groups.items():
            reasons=[r["reasonRetired"].strip() for r in v if r.get("reasonRetired")]
            m=sum(bool(mechanical.fullmatch(x)) for x in reasons)
            i=sum(bool(incident.fullmatch(x)) for x in reasons)
            rows.append([display(k),pct(m,len(v)),len(v),m,i,len(reasons)-m-i])
        rank(section,"Mechanical reliability","Conservative exact-match classification of recorded retirement reasons; unknown reasons remain separate. Incident does not imply driver fault.",rows,["Name","Mechanical retirements %","Starts","Mechanical","Incident","Other/unknown"],reverse=False)
    gaps=[]; circuitgaps=[]
    for race in completed:
        a=[r for r in race["raceResults"] if pos(r) and r.get("gapMillis") is not None and not r.get("gapLaps")]
        if a:
            gaps.append([f'{race["year"]} · {race["grandPrixId"]}',max(r["gapMillis"] for r in a)/1000,len(a)])
    add("Championships","Race field spread","Largest recorded time gap to winner among classified finishers with time gaps, excluding lap gaps; coverage varies.",["Event","Maximum gap seconds","Timed finishers"],gaps)
    add("Circuits","Winning margins by circuit","Recorded winner-to-runner-up gap for same-lap finishes.",["Circuit","Event","Winner","Seconds"],[[circuits.get(r["circuitId"],r["circuitId"]),label,w,sec] for r in completed for label,w,_,sec in margins if label==f'{r["year"]} · {r["grandPrixId"]}'])
    return catalog
