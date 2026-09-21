#!/usr/bin/env python3
"""Build per-player LGC record books from courses.csv and rounds.csv.

Usage:
    python3 compute_stats.py courses.csv rounds.csv stats

The input CSVs remain raw. Generated files are safe to delete and recreate.
"""

import argparse
import ast
import csv
import json
from collections import defaultdict
from pathlib import Path


HOLES = range(1, 19)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("courses_csv", type=Path)
    parser.add_argument("rounds_csv", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    courses = load_courses(args.courses_csv)
    rounds = load_rounds(args.rounds_csv, courses)
    yearly, players, winning_rounds = calculate_all(rounds, courses)
    write_outputs(
        args.output_dir,
        yearly,
        players,
        winning_rounds,
        rounds,
        courses,
    )

    print(f"Created record book for {len(players)} players in {args.output_dir}")


def number(value):
    if value is None or str(value).strip() == "":
        return None
    return int(float(value))


def whole_or_float(value):
    return int(value) if value == int(value) else value


def average(values):
    return round(sum(values) / len(values), 2) if values else None


def parse_players(value):
    """Read a CSV player field such as ["James", "Bon"]."""
    try:
        players = ast.literal_eval(value)
        if isinstance(players, str):
            return [players]
        return [str(player).strip() for player in players]
    except (ValueError, SyntaxError):
        raise ValueError(f"Invalid player list: {value!r}")


def load_courses(path):
    courses = {}

    with path.open(newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            courses[row["course_id"]] = {
                "course_id": row["course_id"],
                "year": int(row["year"]),
                "name": row["course_name"],
                "rating": number(row.get("rating")),
                "slope": number(row.get("slope")),
                "tee": row.get("tee"),
                "par": {
                    hole: number(row[f"hole{hole}_par"])
                    for hole in HOLES
                },
                "yardage": {
                    hole: number(row[f"hole{hole}_yardage"])
                    for hole in HOLES
                },
                "handicap": {
                    hole: number(row[f"hole{hole}_hdcp"])
                    for hole in HOLES
                },
            }

    return courses


def load_rounds(path, courses):
    rounds = []

    with path.open(newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            course = courses.get(row["course_id"])

            if course is None:
                raise ValueError(
                    f"Round {row['round_id']} references unknown "
                    f"course_id {row['course_id']}"
                )

            holes = {
                hole: number(row[f"hole{hole}"])
                for hole in HOLES
            }

            players = parse_players(row["player"])

            gross = sum(
                score for score in holes.values()
                if score is not None
            )

            par = sum(
                course["par"][hole]
                for hole in HOLES
                if holes[hole] is not None
            )

            birdies = sum(
                holes[hole] == course["par"][hole] - 1
                for hole in HOLES
                if holes[hole] is not None
            )

            handicap = number(row.get("handicap"))

            rounds.append({
                "round_id": row["round_id"],
                "year": int(row["year"]),
                "course_id": row["course_id"],
                "course_name": course["name"],
                "players": players,
                "handicap": handicap,
                "holes": holes,
                "gross": gross,
                "par": par,
                "net": gross - handicap if handicap is not None else None,
                "relative_to_par": gross - par,
                "birdies": int(birdies),
                "is_solo": len(players) == 1 and handicap is not None,
                "is_team": len(players) > 1 and handicap is None,
            })

    return rounds


def empty_player():
    return {
        "years_played": set(),

        # Solo statistics
        "solo_rounds": 0,
        "solo_placements": [],
        "net_placements": [],
        "solo_first_placements": 0,
        "total_gross_score": 0,
        "total_net_score": 0,
        "total_birdies": 0,
        "total_eagles": 0,
        "total_pars": 0,
        "total_bogeys": 0,
        "total_dbl_bogeys": 0,
        "total_trp_bogeys": 0,
        "total_qud_bogeys": 0,
        "gross_scores": [],
        "net_scores": [],

        # Team statistics
        "team_rounds": 0,
        "team_placements": [],
        "team_first_placements": 0,
        "total_team_gross_score": 0,
        "total_team_relative_to_par": 0,
        "total_team_birdies": 0,
        "total_team_eagles": 0,
        "total_team_pars": 0,
        "total_team_bogeys": 0,
        "total_team_dbl_bogeys": 0,
        "total_team_trp_bogeys": 0,
        "total_team_qud_bogeys": 0,
        "team_gross_scores": [],

        # Stroke statistics
        "par5_strokes": 0,
        "par5_holes": 0,
        "par4_strokes": 0,
        "par4_holes": 0,
        "par3_strokes": 0,
        "par3_holes": 0,

        "team_par5_strokes": 0,
        "team_par5_holes": 0,
        "team_par4_strokes": 0,
        "team_par4_holes": 0,
        "team_par3_strokes": 0,
        "team_par3_holes": 0,
    }


def calculate_round_metrics(round_data, course):
    """Calculate stroke-based statistics for one round."""
    metrics = {
        "gross_score": round_data["gross"],
        "net_score": round_data["net"],
        "relative_to_par": round_data["relative_to_par"],
        "birdies": 0,
        "eagles": 0,
        "pars": 0,
        "bogeys": 0,
        "double_bogeys": 0,
        "triple_bogeys": 0,
        "quad_bogeys": 0,
        "par3_strokes": 0,
        "par4_strokes": 0,
        "par5_strokes": 0,
        "par3_holes": 0,
        "par4_holes": 0,
        "par5_holes": 0,
    }

    for hole in HOLES:
        strokes = round_data["holes"][hole]
        par = course["par"][hole]

        if strokes is None or par is None:
            continue

        metrics[f"par{int(par)}_strokes"] += strokes
        metrics[f"par{int(par)}_holes"] += 1

        difference = strokes - par

        if difference <= -2:
            metrics["eagles"] += 1
        elif difference == -1:
            metrics["birdies"] += 1
        elif difference == 0:
            metrics["pars"] += 1
        elif difference == 1:
            metrics["bogeys"] += 1
        elif difference == 2:
            metrics["double_bogeys"] += 1
        elif difference == 3:
            metrics["triple_bogeys"] += 1
        elif difference >= 4:
            metrics["quad_bogeys"] += 1

    return metrics


def calculate_all(rounds, courses):
    yearly = defaultdict(lambda: defaultdict(lambda: {
        "handicap": None,
        "gross_score": 0,
        "net_score": None,
        "birdies": 0,
        "eagles": 0,
        "pars": 0,
        "bogeys": 0,
        "double_bogeys": 0,
        "triple_bogeys": 0,
        "quad_bogeys": 0,
        "rounds": 0,
        "team_placement": None,
        "solo_placement": None,
        "net_placement": None,
    }))

    players = defaultdict(empty_player)

    # ---------------------------------------------------------
    # TEAM ROUNDS
    # ---------------------------------------------------------

    team_rounds_by_year = defaultdict(list)

    for round_data in rounds:
        if round_data["is_team"]:
            team_rounds_by_year[round_data["year"]].append(round_data)

    winning_rounds = {}

    for year, team_rounds in team_rounds_by_year.items():
        ranked_teams = rank_items(team_rounds, "gross")

        if ranked_teams:
            winning_rounds[year] = ranked_teams[0][0]

        for team_round, placement in ranked_teams:
            course = courses[team_round["course_id"]]
            metrics = calculate_round_metrics(team_round, course)

            for player in team_round["players"]:
                summary = players[player]

                # Personal participation
                summary["years_played"].add(year)

                # Team placement
                summary["team_rounds"] += 1
                summary["team_placements"].append(placement)

                # Team score statistics
                summary["total_team_gross_score"] += metrics["gross_score"]
                summary["total_team_relative_to_par"] += metrics["relative_to_par"]
                summary["team_gross_scores"].append(metrics["gross_score"])

                # Team scoring statistics
                summary["total_team_birdies"] += metrics["birdies"]
                summary["total_team_eagles"] += metrics["eagles"]
                summary["total_team_pars"] += metrics["pars"]
                summary["total_team_bogeys"] += metrics["bogeys"]
                summary["total_team_dbl_bogeys"] += metrics["double_bogeys"]
                summary["total_team_trp_bogeys"] += metrics["triple_bogeys"]
                summary["total_team_qud_bogeys"] += metrics["quad_bogeys"]

                # Team par-type averages
                for par in (3, 4, 5):
                    summary[f"team_par{par}_strokes"] += metrics[f"par{par}_strokes"]
                    summary[f"team_par{par}_holes"] += metrics[f"par{par}_holes"]

                # Yearly team placement
                yearly[player][year]["team_placement"] = placement

    # ---------------------------------------------------------
    # SOLO ROUND RANKINGS
    # ---------------------------------------------------------

    solo_by_year = defaultdict(list)

    for round_data in rounds:
        if round_data["is_solo"]:
            solo_by_year[round_data["year"]].append(round_data)

    for year, solo_rounds in solo_by_year.items():
        gross_ranked = rank_items(solo_rounds, "gross")
        net_ranked = rank_items(solo_rounds, "net")

        for round_data, placement in gross_ranked:
            player = round_data["players"][0]

            yearly[player][year]["solo_placement"] = placement
            players[player]["solo_placements"].append(placement)

        for round_data, placement in net_ranked:
            player = round_data["players"][0]

            yearly[player][year]["net_placement"] = placement
            players[player]["net_placements"].append(placement)

    # ---------------------------------------------------------
    # SOLO ROUND STATISTICS
    # ---------------------------------------------------------

    for round_data in rounds:
        if not round_data["is_solo"]:
            continue

        player = round_data["players"][0]
        year = round_data["year"]
        course = courses[round_data["course_id"]]

        metrics = calculate_round_metrics(round_data, course)
        record = yearly[player][year]

        # Yearly data
        record["handicap"] = round_data["handicap"]
        record["gross_score"] += metrics["gross_score"]
        record["net_score"] = (
            (record["net_score"] or 0) + metrics["net_score"]
        )
        record["birdies"] += metrics["birdies"]
        record["eagles"] += metrics["eagles"]
        record["pars"] += metrics["pars"]
        record["bogeys"] += metrics["bogeys"]
        record["double_bogeys"] += metrics["double_bogeys"]
        record["triple_bogeys"] += metrics["triple_bogeys"]
        record["quad_bogeys"] += metrics["quad_bogeys"]
        record["rounds"] += 1

        # Player summary
        summary = players[player]
        summary["years_played"].add(year)
        summary["solo_rounds"] += 1

        summary["total_gross_score"] += metrics["gross_score"]
        summary["total_net_score"] += metrics["net_score"]

        summary["total_birdies"] += metrics["birdies"]
        summary["total_eagles"] += metrics["eagles"]
        summary["total_pars"] += metrics["pars"]
        summary["total_bogeys"] += metrics["bogeys"]
        summary["total_dbl_bogeys"] += metrics["double_bogeys"]
        summary["total_trp_bogeys"] += metrics["triple_bogeys"]
        summary["total_qud_bogeys"] += metrics["quad_bogeys"]

        summary["gross_scores"].append(metrics["gross_score"])
        summary["net_scores"].append(metrics["net_score"])

        for par in (3, 4, 5):
            summary[f"par{par}_strokes"] += metrics[f"par{par}_strokes"]
            summary[f"par{par}_holes"] += metrics[f"par{par}_holes"]

    # Count first-place finishes for both formats.
    for player in players:
        players[player]["solo_first_placements"] = (
            players[player]["solo_placements"].count(1)
        )
        players[player]["team_first_placements"] = (
            players[player]["team_placements"].count(1)
        )

    return yearly, players, winning_rounds


def rank_items(items, key):
    """Return (item, place), using competition ranking: 1, 1, 3."""
    ordered = sorted(
        items,
        key=lambda item: (
            item[key]
            if item[key] is not None
            else float("inf")
        ),
    )

    result = []
    previous = object()
    place = 0

    for index, item in enumerate(ordered, start=1):
        if item[key] != previous:
            place = index
            previous = item[key]

        result.append((item, place))

    return result


def build_solo_stats(summary):
    """Build the solo mini-JSON for one player."""
    solo_rounds = summary["solo_rounds"]

    solo = {
        "solo_rounds": solo_rounds,
        "solo_first_places": summary["solo_first_placements"],
        "average_solo_placement": average(summary["solo_placements"]),
        "average_net_placement": average(summary["net_placements"]),

        "total_gross_score": whole_or_float(
            summary["total_gross_score"]
        ),
        "average_gross_score": (
            round(summary["total_gross_score"] / solo_rounds, 2)
            if solo_rounds
            else None
        ),
        "best_gross_score": min(
            summary["gross_scores"],
            default=None,
        ),

        "total_net_score": whole_or_float(
            summary["total_net_score"]
        ),
        "average_net_score": (
            round(summary["total_net_score"] / solo_rounds, 2)
            if solo_rounds
            else None
        ),
        "best_net_score": min(
            summary["net_scores"],
            default=None,
        ),

        "total_eagles": summary["total_eagles"],
        "total_birdies": summary["total_birdies"],
        "total_pars": summary["total_pars"],
        "total_bogeys": summary["total_bogeys"],
        "total_dbl_bogeys": summary["total_dbl_bogeys"],
        "total_trp_bogeys": summary["total_trp_bogeys"],
        "total_qud_bogeys": summary["total_qud_bogeys"],

        "par3_average": (
            round(
                summary["par3_strokes"] /
                summary["par3_holes"],
                2,
            )
            if summary["par3_holes"]
            else None
        ),
        "par4_average": (
            round(
                summary["par4_strokes"] /
                summary["par4_holes"],
                2,
            )
            if summary["par4_holes"]
            else None
        ),
        "par5_average": (
            round(
                summary["par5_strokes"] /
                summary["par5_holes"],
                2,
            )
            if summary["par5_holes"]
            else None
        ),
    }

    solo["birdie_percentage"] = (
        round(
            (
                summary["total_birdies"]
                + summary["total_eagles"]
            )
            / (solo_rounds * 18)
            * 100,
            2,
        )
        if solo_rounds
        else None
    )

    return solo


def build_team_stats(summary):
    """Build the team mini-JSON for one player."""
    team_rounds = summary["team_rounds"]

    team = {
        "team_rounds": team_rounds,
        "team_wins": summary["team_first_placements"],
        "team_first_places": summary["team_first_placements"],
        "average_team_placement": average(
            summary["team_placements"]
        ),

        "total_gross_score": whole_or_float(
            summary["total_team_gross_score"]
        ),
        "average_gross_score": (
            round(
                summary["total_team_gross_score"]
                / team_rounds,
                2,
            )
            if team_rounds
            else None
        ),
        "best_gross_score": min(
            summary["team_gross_scores"],
            default=None,
        ),

        "total_relative_to_par": whole_or_float(
            summary["total_team_relative_to_par"]
        ),
        "average_relative_to_par": (
            round(
                summary["total_team_relative_to_par"]
                / team_rounds,
                2,
            )
            if team_rounds
            else None
        ),

        "total_eagles": summary["total_team_eagles"],
        "total_birdies": summary["total_team_birdies"],
        "total_pars": summary["total_team_pars"],
        "total_bogeys": summary["total_team_bogeys"],
        "total_dbl_bogeys": summary["total_team_dbl_bogeys"],
        "total_trp_bogeys": summary["total_team_trp_bogeys"],
        "total_qud_bogeys": summary["total_team_qud_bogeys"],

        "par3_average": (
            round(
                summary["team_par3_strokes"]
                / summary["team_par3_holes"],
                2,
            )
            if summary["team_par3_holes"]
            else None
        ),
        "par4_average": (
            round(
                summary["team_par4_strokes"]
                / summary["team_par4_holes"],
                2,
            )
            if summary["team_par4_holes"]
            else None
        ),
        "par5_average": (
            round(
                summary["team_par5_strokes"]
                / summary["team_par5_holes"],
                2,
            )
            if summary["team_par5_holes"]
            else None
        ),
    }

    team["birdie_percentage"] = (
        round(
            (
                summary["total_team_birdies"]
                + summary["total_team_eagles"]
            )
            / (team_rounds * 18)
            * 100,
            2,
        )
        if team_rounds
        else None
    )

    return team


def build_yearly_team_stats_csv(player, rounds, courses, output_path):
    """Write the player's team round for each year with the global team placement."""

    team_fields = [
        "year",
        "teammate",
        "score",
        "relative_to_par",
        "eagles",
        "birdies",
        "pars",
        "bogeys",
        "double_bogeys",
        "triple_bogeys",
        "quad_bogeys",
        "team_placement",
        "course_name",
    ]

    # ---------------------------------------------------------
    # Rank ALL team rounds within each year.
    #
    # This must happen before filtering to the selected player,
    # otherwise every player's individual team round would rank
    # as 1st.
    # ---------------------------------------------------------

    team_rounds_by_year = defaultdict(list)

    for round_data in rounds:
        if round_data["is_team"]:
            team_rounds_by_year[round_data["year"]].append(round_data)

    ranked_team_rounds = {}

    for year, year_rounds in team_rounds_by_year.items():
        ranked_team_rounds[year] = rank_items(
            year_rounds,
            "gross",
        )

    # ---------------------------------------------------------
    # Write only the rows involving this player.
    # ---------------------------------------------------------

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=team_fields,
        )

        writer.writeheader()

        for year in sorted(ranked_team_rounds):
            for round_data, placement in ranked_team_rounds[year]:

                if player not in round_data["players"]:
                    continue

                course = courses[round_data["course_id"]]
                metrics = calculate_round_metrics(
                    round_data,
                    course,
                )

                teammates = [
                    teammate
                    for teammate in round_data["players"]
                    if teammate != player
                ]

                writer.writerow({
                    "year": year,
                    "teammate": ", ".join(teammates),
                    "score": metrics["gross_score"],
                    "relative_to_par": metrics["relative_to_par"],
                    "eagles": metrics["eagles"],
                    "birdies": metrics["birdies"],
                    "pars": metrics["pars"],
                    "bogeys": metrics["bogeys"],
                    "double_bogeys": metrics["double_bogeys"],
                    "triple_bogeys": metrics["triple_bogeys"],
                    "quad_bogeys": metrics["quad_bogeys"],
                    "team_placement": placement,
                    "course_name": round_data["course_name"],
                })

def write_outputs(output_dir, yearly, players, winning_rounds, rounds, courses):
    output_dir.mkdir(parents=True, exist_ok=True)

    player_manifest = []

    for player in sorted(players):
        player_dir = (
            output_dir
            / player.lower().replace(" ", "_")
        )
        player_dir.mkdir(exist_ok=True)

        player_manifest.append({
            "name": player,
            "folder": player.lower().replace(" ", "_"),
        })

        # -----------------------------------------------------
        # YEARLY CSV
        # -----------------------------------------------------

        yearly_path = player_dir / "yearly_stats.csv"

        yearly_fields = [
            "year",
            "handicap",
            "gross_score",
            "net_score",
            "birdies",
            "eagles",
            "pars",
            "bogeys",
            "double_bogeys",
            "triple_bogeys",
            "quad_bogeys",
            "solo_placement",
            "net_placement",
            "team_placement",
        ]

        with yearly_path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=yearly_fields,
            )
            writer.writeheader()

            for year in sorted(yearly[player]):
                row = {
                    "year": year,
                    **yearly[player][year],
                }

                writer.writerow({
                    field: row.get(field, 0)
                    for field in yearly_fields
                })
        # -----------------------------------------------------
        # YEARLY TEAM CSV
        # -----------------------------------------------------

        yearly_team_path = player_dir / "yearly_team_stats.csv"
        build_yearly_team_stats_csv(player, rounds, courses, yearly_team_path)

        # -----------------------------------------------------
        # NESTED ALL-TIME JSON
        # -----------------------------------------------------

        summary = players[player]

        all_time = {
            "personal": {
                "player": player,
                "years_played": sorted(
                    summary["years_played"]
                ),
            },
            "solo": build_solo_stats(summary),
            "team": build_team_stats(summary),
        }

        with (
            player_dir / "all_time_stats.json"
        ).open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                all_time,
                file,
                indent=2,
            )

    # ---------------------------------------------------------
    # PLAYER MANIFEST
    # ---------------------------------------------------------

    with (
        output_dir / "players.json"
    ).open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            player_manifest,
            file,
            indent=2,
        )

    # ---------------------------------------------------------
    # WINNING TEAMS
    # ---------------------------------------------------------

    with (
        output_dir / "winning_teams.json"
    ).open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            {
                str(year): {
                    "players": row["players"],
                    "score": whole_or_float(
                        row["gross"]
                    ),
                    "course": row["course_name"],
                }
                for year, row in sorted(
                    winning_rounds.items()
                )
            },
            file,
            indent=2,
        )


if __name__ == "__main__":
    main()