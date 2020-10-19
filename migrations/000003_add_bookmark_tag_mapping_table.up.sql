CREATE TABLE IF NOT EXISTS bookmark_tag_mapping (
    bookmark_id INTEGER NOT NULL REFERENCES  bookmark (_id) ON DELETE CASCADE,
    tag_id VARCHAR(50) NOT NULL REFERENCES tag (_id) ON DELETE CASCADE,
    PRIMARY KEY (bookmark_id, tag_id)
);