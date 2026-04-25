from app.models.schemas import Prediction

_cache: dict[int, Prediction] = {}


def get(fixture_id: int) -> Prediction | None:
    return _cache.get(fixture_id)


def set(fixture_id: int, prediction: Prediction) -> None:
    _cache[fixture_id] = prediction


def get_all() -> dict[int, Prediction]:
    return dict(_cache)
