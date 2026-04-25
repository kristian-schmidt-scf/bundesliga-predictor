from pydantic_settings import BaseSettings, SettingsConfigDict


from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent / ".env",
        env_file_encoding="utf-8"
    )

    # API Keys
    football_data_api_key: str
    odds_api_key: str

    # football-data.org
    football_data_base_url: str = "https://api.football-data.org/v4"
    bundesliga_competition_code: str = "BL1"  # Bundesliga code in football-data.org

    # The Odds API
    odds_api_base_url: str = "https://api.the-odds-api.com/v4"
    odds_sport_key: str = "soccer_germany_bundesliga"
    odds_regions: str = "eu"
    odds_markets: str = "h2h"  # head-to-head (win/draw/loss)
    odds_format: str = "decimal"

    # Dixon-Coles model settings
    # Number of past seasons of data to fit the model on
    seasons_to_fetch: int = 3
    # Time decay half-life in days (recent matches weighted more)
    time_decay_half_life_days: int = 90

    # Scheduled tasks
    # Hour of day (local time, 0-23) to run the daily model refit
    refit_hour: int = 6
    # Interval between odds snapshot polls in seconds (default 12h; free tier has 500 req/month)
    odds_poll_interval_seconds: int = 43200

    # Odds history persistence
    odds_db_path: str = "odds_history.db"  # relative to the backend/ directory

    # User Tipp 11 picks persistence
    picks_db_path: str = "user_picks.db"  # relative to the backend/ directory


settings = Settings()
