import os
import yaml
from dotenv import load_dotenv


# TODO: getopt() for cmd line arguments
class Config:
    tg_token: str
    database_path: str
    ipfs_host: str
    ipfs_port: int
    ipfs_gateway: str
    debug: bool
    log_path: str | None
    agent_config: dict

    def __init__(self):
        # Load the environment variables
        load_dotenv()

        # Set the Telegram token
        tg_token = os.getenv("TG_TOKEN")
        if tg_token is None:
            raise Exception("Setting `TG_TOKEN` is required")
        self.tg_token = tg_token

        # Set the Database URL. Default to in-memory for now
        self.database_path = os.getenv("DATABASE_PATH", ":memory:")

        # Set the log path
        self.log_path = os.getenv("LOG_PATH")

        # Set the IPFS multiaddr
        self.ipfs_host = os.getenv("IPFS_HOST", "localhost")
        self.ipfs_port = int(os.getenv("IPFS_PORT", "5001"))
        self.ipfs_gateway = os.getenv("IPFS_GATEWAY", "http://localhost:8080")

        # Determine if the DEBUG mode is set
        debug = os.getenv("DEBUG", "True")
        self.debug = debug == "True"

        # Read the agent configuration at the path
        agent_config_path = os.getenv("AGENT_CONFIG_PATH", "agent.yaml")

        # Open the configration file for the model
        with open(agent_config_path) as f:
            # Load the config file
            agent_config = yaml.safe_load(f)
        self.agent_config = agent_config
