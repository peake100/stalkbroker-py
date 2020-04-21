import os
import dotenv

from stalkbroker.bot import STALKBROKER


if __name__ == "__main__":
    dotenv.load_dotenv()

    TOKEN = os.getenv("DISCORD_TOKEN")
    STALKBROKER.run(TOKEN)
