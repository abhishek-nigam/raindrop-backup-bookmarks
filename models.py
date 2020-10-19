class Bookmark:
    def __init__(self, _id: str, created_at: str, updated_at: str, link: str, title: str) -> None:
        self._id = _id
        self.created_at = created_at
        self.updated_at = updated_at
        self.link = link
        self.title = title

    def __str__(self) -> str:
        return f"Bookmark({self._id},{self.title})"

    def __repr__(self) -> str:
        return f"Bookmark({self._id},{self.title})"
