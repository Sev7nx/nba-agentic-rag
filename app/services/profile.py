from pathlib import Path

from app.models import UserProfile


class ProfileStore:
    def __init__(self, path: str | Path):
        self._path = Path(path)

    def get(self) -> UserProfile:
        if not self._path.exists():
            return UserProfile()
        try:
            return UserProfile.model_validate_json(self._path.read_text(encoding="utf-8"))
        except Exception:
            return UserProfile()

    def save(self, profile: UserProfile) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(profile.model_dump_json(), encoding="utf-8")