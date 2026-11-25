# GridIQ — Formula 1, by the numbers

Independent static F1 analytics. First module: teammate win rates, session/season filters, career comparisons and Elo ratings.

## Deploy
In Settings → Pages choose GitHub Actions, then run Build and deploy GridIQ from Actions. The workflow downloads the pinned F1DB release, generates site/data.json and publishes site/. No runtime API or backend. To run locally: `python3 scripts/build.py` then `python3 -m http.server --directory site 8000`.

## Data
[F1DB](https://github.com/f1db/f1db), release v2026.21.0, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Derived data, not an official FIA feed. The initial comparison covers 1982 onward, classified positions only, exactly two eligible drivers per constructor/session, no shared cars. Earlier private entrants and unclassified results are not modeled. Elo is exploratory and depends on chronology and opposition. No reliability adjustment yet. Not affiliated with Formula 1 or FIA.

Update the pinned VERSION in scripts/build.py to refresh manually.
