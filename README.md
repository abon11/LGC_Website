# LGC — Lifelong Golf Commitment

The website for the LGC, a yearly golf tournament. Each year has a solo round
(everyone plays their own ball, with a handicap) and a two-person team round;
the team round decides the champions.

The site is a single static page (`index.html`) hosted on GitHub Pages. It has
four tabs:

- **Home** — every player by current handicap, a map with a numbered flag for
  each year's tournament, and all-time totals.
- **Tournament Stats** — one year at a time: winners, rankings, scorecards
  and field statistics.
- **Player Stats** — one player at a time: their record book, charts and rankings.
- **Rules** — the tournament rules.

## What is in this repo

| File | What it is |
|---|---|
| `index.html` | The whole site: markup, styles and code. |
| `courses.csv` | One row per year: the course, where it was, who hosted, and each hole's yardage, par and handicap. **Edited by hand.** |
| `rounds.csv` | One row per scorecard: every solo round and every team round. **Edited by hand.** |
| `compute_stats.py` | Reads the two CSVs and writes the `stats/` folder. |
| `stats/` | Generated per-player record books and the winning teams. **Never edit by hand** — re-run the script instead. |
| `LGCMAP.svg` | The map on the home page (drawn in Inkscape). |
| `LGC_flag.svg` | The flag planted on the map. One drawing is reused for every year; the page swaps in the number. |

The page reads `courses.csv` and `rounds.csv` directly for some things and the
generated `stats/` files for others, so all of them have to be pushed.

## Viewing it locally

The page loads its data files over HTTP, so opening `index.html` by
double-clicking it will not work. From this folder run:

```
python3 -m http.server 8000
```

and open <http://localhost:8000>.

## Adding a new year

### 1. Add the course to `courses.csv`

Add one row. The columns are:

| Column | Meaning |
|---|---|
| `course_id` | The next unused number. Rounds point at this. |
| `year` | The tournament year. |
| `payjumps` | Dollars each net place is worth (lowest net pays 1 × this, next pays 2 × this, ...). |
| `map_x`, `map_y` | Where the flag goes on the map — see step 3. Leave blank for no flag. |
| `host` | Who hosted. |
| `town`, `state` | Where it was played. |
| `course_name`, `rating`, `slope`, `tee` | Straight off the scorecard. |
| `hole1_yardage`, `hole1_par`, `hole1_hdcp` ... `hole18_...` | Yardage, par and handicap for each hole. |

### 2. Add the rounds to `rounds.csv`

Add one row per scorecard:

| Column | Meaning |
|---|---|
| `round_id` | The next unused number. |
| `year`, `course_id` | Must match the row added to `courses.csv`. |
| `player` | A list of names in the same style as the existing rows: `"[""Bon""]"` for a solo round, `"[""Bon"",""Don""]"` for a team round. |
| `handicap` | The player's handicap for a solo round. **Leave blank for a team round** — that is how the two are told apart. |
| `hole1` ... `hole18` | The score on each hole. |
| `p1` (and `p2`, ...) | Playoff holes — see [Playoff holes](#playoff-holes). Blank for almost every row. |

Spell each player's name exactly as in earlier years; a different spelling
becomes a different player. A brand new name simply becomes a new player.

### 3. Find the flag coordinates

1. Open `LGCMAP.svg` in Inkscape.
2. Hover the mouse over the spot where the course is.
3. Read the X and Y shown at the bottom right of the window (units must be px).
4. Put those two numbers in `map_x` and `map_y` for the new row.

The bottom of the flag pole lands on that point. The number on the flag is
worked out automatically: the earliest year in `courses.csv` is 1, the next is
2, and so on.

Do not resize the page of `LGCMAP.svg` in Inkscape (Resize Page to Content and
the like). That shifts every coordinate, and all the existing flags would have
to be re-measured.

### 4. Rebuild the stats

```
python3 compute_stats.py courses.csv rounds.csv stats
```

This rewrites everything in `stats/`. It needs only Python 3, no extra
packages.

### 5. Check it, then push

Look at the site locally (see above): the new flag on the home page, the new
year in Tournament Stats, and a player or two in Player Stats. Then:

```
git add -A
git commit -m "Add 2027"
git push
```

GitHub Pages redeploys on every push to `main`; the live site updates a minute
or so later.

## Playoff holes

If two teams tie for the lowest score in the team round, they replay holes
until one wins. Playoff holes go in extra columns at the end of `rounds.csv`:
`p1` for the first playoff hole, `p2` for the second (add the column to the
header when it is first needed), and so on.

Each entry is the hole that was replayed and the score on it, written as
`{hole, score}`. Because the entry contains a comma it has to be wrapped in
double quotes in the CSV:

```
round_id,year,course_id,player,handicap,hole1,...,hole18,p1
72,2026,4,"[""Bon"",""Don""]",,4,...,5,"{18, 5}"
68,2026,4,"[""Mike"",""Raymond""]",,4,...,5,"{18, 4}"
```

Here both teams replayed hole 18; Mike & Raymond made 4 and Bon & Don made 5,
so Mike & Raymond win. Teams that were not in the playoff leave the cell blank.
If the first hole is also tied, both teams get a `p2` entry.

What a playoff changes:

- **Who wins.** Tied teams are separated by `p1`, then `p2`, and so on. The
  winner places 1st and the loser 2nd, and only the winner gets the win and the
  winnings.
- **Hole-by-hole stats.** A playoff hole counts as one more hole played: it
  adds to birdie / par / bogey counts, par 3 / 4 / 5 averages, birdie
  percentage and the hole charts.
- **Not the round's score.** The 18-hole score, score relative to par and the
  front / back nine totals never include playoff holes.

On Tournament Stats (in Team or Combined mode) a playoff shows as
"Won in a playoff" under the winners, a line under the team ranking with each
team's playoff score, and extra `P1`, `P2`, ... points on the Leaderboard by
Hole chart. It is also noted under the team's scorecard.

If two teams tie for first and no playoff is entered, both are shown as tied
for 1st, so enter the playoff before rebuilding the stats.

## Other things worth knowing

- **Current handicap** on the home page is the handicap on a player's most
  recent solo round.
- **The top 12** on the home page (above the faint line) are the twelve players
  with the most rounds, solo and team combined.
- **Map and flag artwork** can be edited freely in Inkscape as long as the map's
  page size stays the same, the flag's number stays a text object, and the
  bottom of the flag pole stays at the page origin.
- **Flag size** is the `HOME_FLAG_SCALE` constant in `index.html`; how tightly
  the map is cropped is `HOME_MAP_PADDING`.
