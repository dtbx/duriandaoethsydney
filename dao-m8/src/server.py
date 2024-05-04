from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import ipfsApi
import json

from agent import Agent, PromptType
from database import (
    AsyncDatabase,
    Chat,
    Conversation,
)
from logger import Logger
from config import Config

app = FastAPI()

# Configuration
try:
    CONFIG = Config()
    AGENT = Agent(CONFIG.agent_config)
    LOGGER = Logger(CONFIG.log_path, CONFIG.debug)
    IPFS = ipfsApi.Client(CONFIG.ipfs_host, CONFIG.ipfs_port)
    DATABASE = AsyncDatabase(CONFIG.database_path)
except Exception as e:
    raise Exception(f"Error loading configuration: {e}")


# Pydantic models
class ProposalRequest(BaseModel):
    intent: str
    ipfs_hash: str


class ProposalResponse(BaseModel):
    ipfs_hash: str


class TranscriptResponse(BaseModel):
    id: int
    agenda: str
    ipfs_hash: str


class PyUser(BaseModel):
    username: str | None
    first_name: str | None
    last_name: str | None


class PyReplyToMessage(BaseModel):
    from_user: PyUser


class PyMessage(BaseModel):
    from_user: PyUser
    reply_to_message: PyReplyToMessage | None
    text: str


@app.get("/api/transcripts")
async def get_transcripts(dao_addr: str, chain_id: int):
    request_method = "GET"
    request_url = "/api/transcripts"
    span = LOGGER.get_request_span(request_method, request_url)
    span.info(f"DAO: {dao_addr}, Chain ID: {chain_id}")
    async with DATABASE.AsyncSession() as session:
        async with session.begin():
            try:
                chat = await Chat.read_by_dao(dao_addr, chain_id, session, span)
                if chat is None:
                    raise HTTPException(status_code=404, detail="Chat not found")

                conversations = await Conversation.read_pushed(chat.id, session, span)
                return [
                    TranscriptResponse(id=c.id, agenda=c.agenda, ipfs_hash=c.ipfs_hash)
                    for c in conversations
                ]
            except Exception as e:
                span.error(f"Error getting transcripts: {e}")
                if isinstance(e, HTTPException):
                    raise e
                raise HTTPException(
                    status_code=500,
                    detail="An error occurred while fetching transcripts",
                )


@app.post("/api/propose")
async def propose(proposal: ProposalRequest):
    request_method = "POST"
    request_url = "/api/propose"
    span = LOGGER.get_request_span(request_method, request_url)
    span.info(f"Proposal: {proposal}")
    async with DATABASE.AsyncSession() as session:
        async with session.begin():
            try:
                # Fetch the conversation from IPFS
                # TODO: this is not working for some reason
                # conversation_data = IPFS.cat(proposal.ipfs_hash)
                # Make get request to IPFS gateway
                import requests

                conversation_data = requests.get(
                    f"{CONFIG.ipfs_gateway}/ipfs/{proposal.ipfs_hash}"
                ).text
                conversation = json.loads(conversation_data)

                span.info(f"Proposing: {conversation}")

                agenda_message = {
                    "from_user": {
                        "username": "agenda",
                        "first_name": None,
                        "last_name": None,
                    },
                    "reply_to_message": None,
                    "text": conversation["agenda"],
                }
                intent_message = {
                    "from_user": {
                        "username": "intent",
                        "first_name": None,
                        "last_name": None,
                    },
                    "reply_to_message": None,
                    "text": proposal.intent,
                }

                messages = [agenda_message]
                for message in conversation["messages"]:
                    messages.append(message)
                messages.append(intent_message)

                pyMessages = []
                for message in messages:
                    pyMessages.append(
                        PyMessage(
                            from_user=PyUser(
                                username=message["from_user"]["username"],
                                first_name=message["from_user"]["first_name"],
                                last_name=message["from_user"]["last_name"],
                            ),
                            reply_to_message=PyReplyToMessage(
                                from_user=PyUser(
                                    username=message["reply_to_message"]["from_user"][
                                        "username"
                                    ],
                                    first_name=message["reply_to_message"]["from_user"][
                                        "first_name"
                                    ],
                                    last_name=message["reply_to_message"]["from_user"][
                                        "last_name"
                                    ],
                                )
                            )
                            if message["reply_to_message"]
                            else None,
                            text=message["text"],
                        )
                    )

                # Generate the proposal
                pyMessages.reverse()
                text = ""
                import random

                # need an int and im lazy
                rand_id = random.randint(0, 1000000)
                try:
                    async for content, _ in AGENT.yield_response(
                        pyMessages, rand_id, PromptType.proposal, span=span
                    ):
                        if content == "":
                            span.warn("Empty response from agent")
                            continue
                        text += content
                except Exception as e:
                    span.error(f"Error generating summary: {e}")
                    raise e

                ipfs_hash = IPFS.add_str(text)
                span.info(f"Proposal: {ipfs_hash}")

                return ProposalResponse(ipfs_hash=ipfs_hash)
            except Exception as e:
                span.error(f"Error proposing: {e}")
                raise HTTPException(
                    status_code=500, detail="An error occurred while proposing"
                )


if __name__ == "__main__":
    import uvicorn

    LOGGER.info("Starting server")

    uvicorn.run(app, host="0.0.0.0", port=8000)
