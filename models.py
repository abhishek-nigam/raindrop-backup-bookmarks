from typing import List


class Tag:
    '''
        Model for tag
    '''
    def __init__(self, _id: str) -> None:
        self._id = _id

    def __str__(self) -> str:
        return f"Tag({self._id})"

    def __repr__(self) -> str:
        return f"Tag({self._id})"


class BookmarkTagMapping:
    '''
        Model for bookmark tag mapping
    '''
    def __init__(self, bookmark_id: str, tag_id: str) -> None:
        self.bookmark_id = bookmark_id
        self.tag_id = tag_id

    def __str__(self) -> str:
        return f"BookmarkTagMapping({self.bookmark_id},{self.tag_id})"

    def __repr__(self) -> str:
        return f"BookmarkTagMapping({self.bookmark_id},{self.tag_id})"


class Bookmark:
    '''
        Model for bookmark
    '''
    def __init__(self, _id: str, created_at: str, updated_at: str, link: str, title: str, tags: List[Tag], mappings: List[BookmarkTagMapping]) -> None:
        self._id = _id
        self.created_at = created_at
        self.updated_at = updated_at
        self.link = link
        self.title = title
        self.tags = tags
        self.mappings = mappings # bookmark tag mappings

    def __str__(self) -> str:
        return f"Bookmark({self._id},{self.title},{len(self.tags)} tags)"

    def __repr__(self) -> str:
        return f"Bookmark({self._id},{self.title},{len(self.tags)} tags)"
