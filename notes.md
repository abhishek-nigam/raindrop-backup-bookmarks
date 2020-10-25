- Generate requirements.txt file (excluding autopep8 and its depedency pycodestype). WARNING: This will remove the platform condition in the file
  `pip freeze | grep -v 'autopep8\|pycodestyle' | > requirements.txt`

- Generate migations using golang-migrate too
  `migrate create -dir ./migrations -ext .sql -seq migration_name`

- Run UP migrations
  `migrate -source file://migrations -database postgres_connection_string up`

- Sample SQL to view bookmarks and tags
  `select _id, created_at, updated_at, left(title, 30) as title, left(link, 30) as link, string_agg(tag_id,',') as tags from bookmark b inner join bookmark_tag_mapping btm on b._id = btm.bookmark_id group by _id;`