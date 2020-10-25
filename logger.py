import logging

logger = logging.getLogger(__name__)

c_handler = logging.StreamHandler()

c_format = logging.Formatter('%(levelname)s - %(asctime)s - %(message)s')
c_handler.setFormatter(c_format)

logger.addHandler(c_handler)
logger.setLevel(level=logging.INFO)
