- Generate requirements.txt file (excluding autopep8 and its depedency pycodestype)**
`pip freeze | grep -v 'autopep8\|pycodestyle' | > requirements.txt`

- Generate migations using golang-migrate too
`migrate create -dir ./migrations -ext .sql -seq migration_name`

- Run UP migrations
`migrate -source file://migrations -database postgres_connection_string up`