# Script for backing up bookmarks stored in [Raindrop.io](https://raindrop.io/)

This uses [Raindrop.io API](https://developer.raindrop.io/)
<br><br>
It uses PostgreSQL for backup.
<br>
It is developed in Python 3.8.3. Refer to [requirements.txt](./requirements.txt) for Python package dependencies.
<br><br>
Entrypoint is [run.py](./run.py) file. Available command line args can be found by `python run.py --help`
<br><br>
It requires the following config values to be set in environement variables or available via .env file in project root directory:

- RAINDROP_IO_TOKEN
- POSTGRES_USERNAME
- POSTGRES_PASSWORD
- POSTGRES_HOST
- POSTGRES_PORT

### Development

Want to contribute? Great! Fork me!

### License

MIT

### Say Hi

[Email: abhisheknigam1996@gmail.com](mailto://abhisheknigam1996@gmail.com)<br>
[LinkedIn](https://www.linkedin.com/in/iabhishek25/)
