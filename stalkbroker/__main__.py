import dotenv
import sys
import logging
from stalkbroker import bot

if __name__ == "__main__":
    logging.info(f"Python Version: {sys.version}")
    dotenv.load_dotenv()
    bot.run_stalkbroker()
