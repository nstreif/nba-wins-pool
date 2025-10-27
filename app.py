#!/usr/bin/env python3
# coding: utf-8
"""
Streamlit app for fetching NBA standings and displaying participant win totals.
Calculates standings dynamically from game results (regular season only).
No stored files — real computed daily data.
"""

from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import os
from nba_api.stats.endpoints import leaguegamefinder

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

BANNER_PATH = "banner.png"
CURRENT_SEASON = "2025-26"

PARTICIPANT_TEAMS = {
    "Zack": ["Cavaliers", "Mavericks", "Pistons", "Hornets"],
    "Ryan": ["Thunder", "Bucks", "Hawks", "Bulls"],
    "Streif": ["Knicks", "Lakers", "Raptors", "76ers"],
    "Doug": ["Rockets", "Timberwolves", "Grizzlies", "Heat"],
    "Chris": ["Nuggets", "Spurs", "Warriors", "Trail Blazers"],
    "Matt": ["Magic", "Celtics", "Clippers", "Pacers"]
}

# ---------------------------------------------------------------------------
# DATA FETCHING
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def fetch_standings_for_date(date_str: str) -> pd.DataFrame:
    """
    Compute NBA standings as of a given date using leaguegamefinder.
    Filters to 2025-26 regular season games up to the provided date.
    """
    try:
        games = leaguegamefinder.LeagueGameFinder(season_nullable=CURRENT_SEASON).get_data_frames()[0]
        games['GAME_DATE'] = pd.to_datetime(games['GAME_DATE'])
        cutoff = datetime.fromisoformat(date_str)
        games = games[games['GAME_DATE'] <= cutoff]

        # ✅ Filter out preseason and playoffs by GAME_ID prefix
        games = games[games['GAME_ID'].astype(str).str.startswith("002")]

        # Determine winners
        games['WINNER'] = games.apply(lambda x: x['TEAM_NAME'] if x['WL'] == 'W' else None, axis=1)

        # Count wins per team
        wins = games['WINNER'].value_counts().reset_index()
        wins.columns = ['team', 'wins']

        return wins.sort_values(by='wins', ascending=False).reset_index(drop=True)

    except Exception as e:
        st.error(f"Error fetching standings for {date_str}: {e}")
        return pd.DataFrame(columns=['team', 'wins'])

def calculate_totals(df: pd.DataFrame) -> pd.Series:
    """Sum total wins for each participant based on selected teams."""
    totals = {}
    for participant, teams in PARTICIPANT_TEAMS.items():
        mask = df['team'].apply(lambda t: any(team.lower() in t.lower() for team in teams))
        totals[participant] = df.loc[mask, 'wins'].sum()
    return pd.Series(totals, name='Win Total')


@st.cache_data(ttl=3600)
def fetch_history(start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch historical participant totals by recomputing standings for each date."""
    start = datetime.fromisoformat(start_date).date()
    end = datetime.fromisoformat(end_date).date()
    days = (end - start).days + 1
    history = []

    progress_bar = st.progress(0)
    for i in range(days):
        progress_bar.progress((i + 1) / days)
        date_str = (start + timedelta(days=i)).isoformat()
        standings = fetch_standings_for_date(date_str)
        if standings.empty:
            continue
        totals = calculate_totals(standings)
        entry = {**totals.to_dict(), 'date': date_str}
        history.append(entry)
    progress_bar.empty()

    df = pd.DataFrame(history)
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
    return df

# ---------------------------------------------------------------------------
# STREAMLIT APP
# ---------------------------------------------------------------------------

def main():
    if os.path.isfile(BANNER_PATH):
        st.image(BANNER_PATH, use_container_width=True)

    st.title("🏀 Chill and Cool Guys NBA Wins Pool")

    today = datetime.today()
    end_date = today.date()

    with st.spinner("Calculating current NBA standings..."):
        standings_df = fetch_standings_for_date(end_date.isoformat())

    if standings_df.empty:
        st.warning("No standings data available yet for this season.")
        return

    totals = calculate_totals(standings_df)

    # Optional standings
    if st.checkbox("Show NBA Standings Table"):
        st.dataframe(standings_df)

    # Bar chart of current totals
    st.subheader("Current Participant Win Totals")
    fig1, ax1 = plt.subplots()
    totals.sort_values(ascending=False).plot(kind="bar", ax=ax1, rot=45)
    ax1.bar_label(ax1.containers[0])
    ax1.set_ylabel("Wins")
    st.pyplot(fig1)

    # Historical chart
    st.subheader("Participant Win Totals Over Time")
    time_range = st.radio(
        "Select time range:",
        ["Past 30 Days", "Past 14 Days", "Past Week"],
        horizontal=True,
        index=0
    )

    if time_range == "Past Week":
        start_date = (today - timedelta(days=7)).date()
    elif time_range == "Past 14 Days":
        start_date = (today - timedelta(days=14)).date()
    else:
        start_date = (today - timedelta(days=30)).date()

    with st.spinner("Recomputing standings for each day..."):
        history = fetch_history(start_date.isoformat(), end_date.isoformat())

    if not history.empty:
        fig2, ax2 = plt.subplots()
        history.plot(marker='', ax=ax2)
        ax2.set_ylabel("Total Wins")
        ax2.set_xlabel("Date")
        st.pyplot(fig2)
    else:
        st.info("No historical data available for this period.")

if __name__ == "__main__":
    main()
