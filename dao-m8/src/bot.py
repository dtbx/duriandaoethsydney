import asyncio
import ipfsApi
import json

from telebot import types as telebot_types, async_telebot

from database import (
    AsyncDatabase,
    Chat,
    Message,
    Conversation,
    ConversationState,
    Summary,
    SummaryState,
    DatabaseException,
    DatabaseError,
)
from logger import Logger
from agent import Agent, PromptType
from config import Config

## Configuration Constants ##

# Telegram Chat Commands
# NOTE: regardless of what commands you write, they will not be accessible to the user unless you register them here!
BOT_COMMANDS = [
    # Misc
    ("help", "Show the help menu"),
    ("info", "Show information about the bot"),
    (
        "start",
        "Configure the bot and install it on the chat.\n"
        + " ex: /start <dao_address> <chain_id>\n"
        + " args:\n"
        + "    - dao_address: The address of the DAO contract\n"
        + "    - chain_id: The chain ID where it's deployed",
    ),
    # Conversation Management
    (
        "new",
        "Create a new conversation"
        + "\n"
        + "  ex: /new <agenda>"
        + "\n"
        + "  Args:"
        + "\n"
        + "    - agenda: The agenda of the conversation",
    ),
    ("ls", "List all conversations"),
    (
        "enter",
        "Enter an inactive conversation for continued discussion\n"
        + "  ex: /enter <conversation_id>\n"
        + "  Args:\n"
        + "    - conversation_id: The id of the conversation to enter",
    ),
    ("exit", "Exit the current conversation"),
    ("end", "End the current conversation. This will post a transcript to Ipfs"),
    (
        "cancel",
        "Cancel the current conversation. This will not post a transcript to Ipfs",
    ),
    (
        "push",
        "Push a complete conversation transcript on Ipfs"
        + "\n"
        + "  ex: /push <conversation_id>"
        + "\n"
        + "  Args:"
        + "\n"
        + "    - conversation_id: The id of the conversation to push",
    ),
    # Converaation Tools
    ("summary", "Summarize the current conversation up till now"),
]

## State ##
CONFIG = Config()
LOGGER = Logger(CONFIG.log_path, CONFIG.debug)

try:
    LOGGER.info("Setting up Bot...")
    BOT = async_telebot.AsyncTeleBot(CONFIG.tg_token)
    LOGGER.info("Setting up AsyncDatabase...")
    DATABASE = AsyncDatabase(CONFIG.database_path)
    LOGGER.info("Setting up Agent...")
    AGENT = Agent(CONFIG.agent_config)

    # TODO: make this configurable
    IPFS = ipfsApi.Client(CONFIG.ipfs_host, CONFIG.ipfs_port)
except Exception as e:
    LOGGER.error(f"An unexpected error occurred during setup: {e}")
    raise e

## State Management ##


# Set the bot's actual name and all of the potential names it might be called
def set_bot_name(name: str):
    # Set the name of the bot on the agent -- this is it's telegram username and persona name
    AGENT.set_name(name)


## Handlers ##

# Misc Commands


@BOT.message_handler(commands=["start"])
async def start_command_handler(message: telebot_types.Message):
    """
    Send a welcome message to the user when they start a conversation with the bot.
    """
    # Log the command
    span = LOGGER.get_message_span(message)
    span.info("/start command called")
    chat_id = message.chat.id

    # Extract <dao_address> and <chain_id> from the message
    if len(message.text.split(" ")) < 3:
        await BOT.reply_to(
            message,
            "Please provide the DAO address and chain ID: /start <dao_address> <chain_id>",
        )
        return None

    try:
        # TODO: validate the dao_address
        dao_address = message.text.split(" ")[1]
        chain_id = int(message.text.split(" ")[2])
    except ValueError:
        await BOT.reply_to(
            message,
            "Please provide a valid chain ID: /start <dao_address> <chain_id>",
        )
        return None

    async with DATABASE.AsyncSession() as session:
        async with session.begin():
            try:
                await Chat.create(chat_id, dao_address, chain_id, session, span=span)
                await BOT.reply_to(
                    message,
                    "Welcome to DaoM8 Bot! Your chat has been created. Please type /new to start a new conversation.",
                )
                await session.commit()
            except Exception as e:
                await session.rollback()
                span.error(f"Error handling /start command: {e}")
                if isinstance(e, DatabaseException):
                    db_error = e.db_error
                    if db_error == DatabaseError.conflict:
                        await BOT.reply_to(
                            message,
                            "This chat already exists. Please type /new to start a new conversation.",
                        )
                else:
                    await BOT.reply_to(
                        message,
                        "An unknown error occurred while creating the chat. Woops!",
                    )
            finally:
                return None


@BOT.message_handler(commands=["help"])
async def help_command_handler(message: telebot_types.Message):
    """
    Send a message to the user with a list of commands and their descriptions.
    """
    # Log the command
    span = LOGGER.get_message_span(message)
    span.info("/help command called")
    try:
        # Send the message to the user
        help_text = "The following commands are available:\n\n"
        for command, description in BOT_COMMANDS:
            help_text += f"/{command} - {description}\n"
        await BOT.reply_to(message, help_text)

        # Ok
        return None
    except Exception as e:
        span.error(f"Error handling /help command: {e}")
        return None


@BOT.message_handler(commands=["info"])
async def info_command_handler(message: telebot_types.Message):
    """
    Send a message to the user with information about the bot.
    """
    # Log the command
    span = LOGGER.get_message_span(message)
    span.info("/info command called")
    try:
        # Send the message to the user
        await BOT.reply_to(
            message,
            "DaoM8 Bot is a tool for creating, summarizing, and proposing conversations to a DAO.",
        )
        # Ok
        return None
    except Exception as e:
        span.error(f"Error handling /info command: {e}")
        return None


## Conversation Management Commands


@BOT.message_handler(commands=["new"])
async def new_command_handler(message: telebot_types.Message):
    """
    Start a new conversation with the bot.
    """
    # Log the command
    span = LOGGER.get_message_span(message)
    span.info("/new command called")

    chat_id = message.chat.id

    # Extract the agenda from the message
    # This should be everything after the command
    agenda = message.text.split(" ")[1:]
    if len(agenda) == 0:
        await BOT.reply_to(message, "Please provide an agenda:\n" + "ex: /new <agenda>")
        return None

    agenda = [word for word in agenda if word != ""]
    agenda = " ".join(agenda)

    async with DATABASE.AsyncSession() as session:
        async with session.begin():
            try:
                # Check if the chat is set up
                chat = await Chat.read(chat_id, session, span=span)
                if chat is None:
                    await BOT.reply_to(
                        message,
                        "The chat has not been set up. Please type /start to set up the chat.",
                    )
                    return None

                conersation = await Conversation.create(
                    chat_id, agenda, session, span=span
                )
                if conersation is None:
                    await BOT.reply_to(
                        message,
                        "You already have an active conversation. Please end it before starting a new one.",
                    )
                    return None
                await BOT.reply_to(
                    message,
                    "A new conversation has been started. Please type /complete to end the conversation."
                    + "\n"
                    + "You can also type /exit to exit the conversation while saving your progress."
                    + "\n"
                    "Agenda: " + agenda,
                )
                await session.commit()
            except Exception as e:
                await session.rollback()
                span.error(f"Error handling /new command: {e}")
                await BOT.reply_to(
                    message,
                    "An unknown error occurred while starting the conversation. Woops!",
                )
            finally:
                return None


@BOT.message_handler(commands=["ls"])
async def ls_command_hander(message: telebot_types.Message):
    """
    List all conversations
    """

    span = LOGGER.get_message_span(message)
    span.info("/ls command called")
    chat_id = message.chat.id

    async with DATABASE.AsyncSession() as session:
        async with session.begin():
            try:
                conversations = await Conversation.read_all(chat_id, session, span=span)
                if len(conversations) == 0:
                    await BOT.reply_to(message, "You don't have any conversations.")
                    return None
                reply = "Your conversations are:\n"
                for conversation in conversations:
                    reply += f"{conversation.id}:\n - Agenda: {conversation.agenda}\n - Status: {str(conversation.state)}\n\n"
                    if conversation.ipfs_hash is not None:
                        reply += (
                            f" - Record pushed to IPFS @ {conversation.ipfs_hash}\n\n"
                        )
                await BOT.reply_to(message, reply)
            except Exception as e:
                span.error(f"Error handling /ls command: {e}")
                await BOT.reply_to(
                    message,
                    "An unknown error occurred while listing the conversations.",
                )
            finally:
                return None


@BOT.message_handler(commands=["enter"])
async def enter_command_handler(message: telebot_types.Message):
    """
    Enter an inactive conversation if there is not an active one.
    """

    span = LOGGER.get_message_span(message)
    span.info("/enter command called")

    chat_id = message.chat.id

    # Extract the conversation ID from the message
    # This should be the first word after the command
    conversation_id = message.text.split(" ")[1]
    conversation_id = int(conversation_id)

    async with DATABASE.AsyncSession() as session:
        async with session.begin():
            try:
                # Check if the chat is set up
                chat = await Chat.read(chat_id, session, span=span)
                if chat is None:
                    await BOT.reply_to(
                        message,
                        "The chat has not been set up. Please type /start to set up the chat.",
                    )
                    return None

                # Check that we don't have an active session
                active_conversation = await Conversation.active(
                    chat_id, session, span=span
                )
                if active_conversation is not None:
                    await BOT.reply_to(
                        message,
                        "You already have an active conversation. Please end it before entering another new one.",
                    )
                    return None
                # Enter the conversation
                conversation = await Conversation.enter(
                    chat_id, conversation_id, session, span=span
                )
                if conversation is None:
                    await BOT.reply_to(message, "The conversation does not exist.")
                    return None
                await BOT.reply_to(
                    message,
                    "You have entered the conversation. Please type /exit to exit the conversation."
                    + "\n"
                    "You may call /summary to catch up on the conversation so far."
                    + "\n"
                    "Agenda: " + conversation.agenda,
                )
                await session.commit()
            except Exception as e:
                await session.rollback()
                span.error(f"Error handling /enter command: {e}")
                await BOT.reply_to(
                    message,
                    "An unknown error occurred while entering the conversation. Woops!",
                )
            finally:
                return None


@BOT.message_handler(commands=["exit"])
async def exit_command_handler(message: telebot_types.Message):
    """
    Exit the current conversation with the bot.
    """

    span = LOGGER.get_message_span(message)
    span.info("/exit command called")

    chat_id = message.chat.id

    async with DATABASE.AsyncSession() as session:
        async with session.begin():
            try:
                # Check if the chat is set up
                chat = await Chat.read(chat_id, session, span=span)
                if chat is None:
                    await BOT.reply_to(
                        message,
                        "The chat has not been set up. Please type /start to set up the chat.",
                    )
                    return None

                conversation = await Conversation.update_state(
                    chat_id, ConversationState.inactive, session, span=span
                )
                if conversation is None:
                    await BOT.reply_to(
                        message, "You don't have an active conversation to exit."
                    )
                    return None
                await BOT.reply_to(
                    message,
                    "The conversation has been exited. You can enter it again using /enter "
                    + str(conversation.id),
                )
                await session.commit()
            except Exception as e:
                await session.rollback()
                span.error(f"Error handling /exit command: {e}")
                await BOT.reply_to(
                    message,
                    "An unknown error occurred while exiting the conversation. Woops!",
                )
            finally:
                return None


@BOT.message_handler(commands=["cancel"])
async def cancel_command_handler(message: telebot_types.Message):
    """
    Cancel the current conversation with the bot.
    """

    span = LOGGER.get_message_span(message)
    span.info("/cancel command called")

    chat_id = message.chat.id

    async with DATABASE.AsyncSession() as session:
        async with session.begin():
            try:
                # Check if the chat is set up
                chat = await Chat.read(chat_id, session, span=span)
                if chat is None:
                    await BOT.reply_to(
                        message,
                        "The chat has not been set up. Please type /start to set up the chat.",
                    )
                    return None

                conversation = await Conversation.update_state(
                    chat_id, ConversationState.cancelled, session, span=span
                )
                if conversation is None:
                    await BOT.reply_to(
                        message, "You don't have an active conversation to cancel."
                    )
                    return None
                await BOT.reply_to(
                    message,
                    "The conversation has been cancelled: " + str(conversation.id),
                )
                await session.commit()
            except Exception as e:
                await session.rollback()
                span.error(f"Error handling /exit command: {e}")
                await BOT.reply_to(
                    message,
                    "An unknown error occurred while cancelling the conversation. Woops!",
                )
            finally:
                return None


@BOT.message_handler(commands=["complete"])
async def complete_command_handler(message: telebot_types.Message):
    """
    Cancel the current conversation with the bot.
    """

    span = LOGGER.get_message_span(message)
    span.info("/complete command called")

    chat_id = message.chat.id

    async with DATABASE.AsyncSession() as session:
        async with session.begin():
            try:
                # Check if the chat is set up
                chat = await Chat.read(chat_id, session, span=span)
                if chat is None:
                    await BOT.reply_to(
                        message,
                        "The chat has not been set up. Please type /start to set up the chat.",
                    )
                    return None

                conversation = await Conversation.update_state(
                    chat_id, ConversationState.complete, session, span=span
                )
                if conversation is None:
                    await BOT.reply_to(
                        message, "You don't have an active conversation to complete."
                    )
                    return None
                await BOT.reply_to(
                    message,
                    "The conversation has been completed! Congrats on the productive conversation! You can new push to ipfs using /push "
                    + str(conversation.id),
                )
                await session.commit()
            except Exception as e:
                await session.rollback()
                span.error(f"Error handling /complete command: {e}")
                await BOT.reply_to(
                    message,
                    "An unknown error occurred while completing the conversation. Woops!",
                )
            finally:
                return None


@BOT.message_handler(commands=["push"])
async def push_command_handler(message: telebot_types.Message):
    """
    Summarize the current conversation with the bot.
    Marks the conversation as complete and dispatches a job to summarize the conversation.
    """

    span = LOGGER.get_message_span(message)
    span.info("/push command called")
    chat_id = message.chat.id

    if len(message.text.split(" ")) < 2:
        await BOT.reply_to(
            message, "Please provide a conversation ID: /push <conversation_id>"
        )
        return None
    try:
        conversation_id = message.text.split(" ")[1]
        conversation_id = int(conversation_id)
    except ValueError:
        await BOT.reply_to(
            message, "Please provide a valid conversation ID: /push <conversation_id>"
        )
        return None

    # Initalize a new json blob to store the conversation
    async with DATABASE.AsyncSession() as session:
        async with session.begin():
            try:
                # Check if the chat is set up
                chat = await Chat.read(chat_id, session, span=span)
                if chat is None:
                    await BOT.reply_to(
                        message,
                        "The chat has not been set up. Please type /start to set up the chat.",
                    )
                    return None

                conversation = await Conversation.read(
                    chat_id, conversation_id, session, span=span
                )
                if conversation is None:
                    await BOT.reply_to(message, "The conversation does not exist")
                    return None
                elif conversation.state != ConversationState.complete:
                    await BOT.reply_to(
                        message,
                        "The conversation is not complete. Please end it before pushing it to IPFS.",
                    )
                    return None
                elif conversation.ipfs_hash is not None:
                    await BOT.reply_to(
                        message,
                        "The conversation has already been pushed to IPFS. You can find it at: "
                        + conversation.ipfs_hash,
                    )
                    return None
                data = {}
                data["agenda"] = conversation.agenda
                db_messages = await Message.read_all(
                    conversation.id, session, span=span
                )
                messages = []
                for m in db_messages:
                    messages.append(
                        {
                            "from_user": {
                                "username": m.from_user.username,
                                "first_name": m.from_user.first_name,
                                "last_name": m.from_user.last_name,
                            },
                            "reply_to_message": {
                                "from_user": {
                                    "username": m.from_user.username,
                                    "first_name": m.from_user.first_name,
                                    "last_name": m.from_user.last_name,
                                }
                            }
                            if m.reply_to_message is not None
                            else None,
                            "text": m.text,
                        }
                    )

                messages.reverse()
                data["messages"] = messages

                # Push the conversation to IPFS
                ipfs_hash = IPFS.add_str(json.dumps(data))

                # Update the conversation with the IPFS hash
                await Conversation.set_ipfs_hash(
                    conversation.id, ipfs_hash, session, span=span
                )
                await BOT.reply_to(
                    message,
                    "Transcript of the conversation has been pushed to Ipfs @ "
                    + ipfs_hash,
                )
                await session.commit()
            except Exception as e:
                span.error(f"Error handling /push command: {e}")
                await BOT.reply_to(
                    message,
                    "An unknown error occurred while pushing the conversation to IPFS. Woops!",
                )
            return None


# Conversation Tools


@BOT.message_handler(commands=["summary"])
async def summary_command_handler(message: telebot_types.Message):
    """
    Summarize the current conversation with the bot.
    Marks the conversation as complete and dispatches a job to summarize the conversation.
    """

    span = LOGGER.get_message_span(message)
    span.info("/summary command called")
    chat_id = message.chat.id

    summary = None
    async with DATABASE.AsyncSession() as session:
        async with session.begin():
            try:
                # Check if the chat is set up
                chat = await Chat.read(chat_id, session, span=span)
                if chat is None:
                    await BOT.reply_to(
                        message,
                        "The chat has not been set up. Please type /start to set up the chat.",
                    )
                    return None

                # Check if the user has an active conversation
                conversation = await Conversation.active(chat_id, session, span=span)
                if conversation is None:
                    await BOT.reply_to(
                        message, "You don't have an active conversation to summarize."
                    )
                    return None

                # Attempt to create a summary
                summary = await Summary.create(conversation.id, session, span=span)
                if summary is None:
                    await BOT.reply_to(
                        message,
                        "An error occurred while creating the summary. Please try again later.",
                    )
                    return None

                reply = await BOT.reply_to(message, "Generating a summary...")

                # Get the most recent messages from the conversation
                messages = await Message.read_all(
                    conversation.id,
                    session,
                    limit=summary.message_count,
                    span=span,
                )

                await session.commit()
            except Exception as e:
                await session.rollback()
                span.error(f"Error handling /summary command: {e}")
                await BOT.reply_to(
                    message, "An error occurred while summarizing the conversation."
                )
                return None

    # Generate the summary
    text = ""
    summary_state = SummaryState.complete
    try:
        async for content, _ in AGENT.yield_response(
            messages, summary.conversation_id, PromptType.summary, span=span
        ):
            if content == "":
                span.warn("Empty response from agent")
                continue
            text += content
            result = "Summary ID: " + str(summary.id) + text + "..." + "\n\n"
            await BOT.edit_message_text(
                result, chat_id=chat_id, message_id=reply.message_id
            )
    except Exception as e:
        span.error(f"Error generating summary: {e}")
        summary_state = SummaryState.failed
    finally:
        async with DATABASE.AsyncSession() as session:
            async with session.begin():
                try:
                    await Summary.mark(
                        summary.id, text, summary_state, session, span=span
                    )
                    await session.commit()
                except Exception as e:
                    await session.rollback()
                    span.error(f"Error marking summary: {e}")
                    await BOT.reply_to(
                        message, "An error occurred while summarizing the conversation."
                    )
    try:
        if summary_state == SummaryState.failed:
            text = "An error occurred while generating the summary. Please try again later."
        else:
            text = "Summary id: " + str(summary.id) + text
        await BOT.edit_message_text(text, chat_id=chat_id, message_id=reply.message_id)
    except Exception as e:
        span.error(f"Error sending summary: {e}")
        await BOT.reply_to(
            message, "An error occurred while summarizing the conversation."
        )
    finally:
        return None


# Message Type Handlers


@BOT.message_handler(content_types=["text"])
async def text_message_handler(message: telebot_types.Message):
    """
    Handle all text messages.
    Use the agent to construct an informed response
    """
    # Log the message
    span = LOGGER.get_message_span(message)
    span.info("Received text message")

    async with DATABASE.AsyncSession() as session:
        async with session.begin():
            try:
                # Check if the message is part of an active conversation
                active_conversation = await Conversation.active(
                    message.chat.id, session, span=span
                )

                if active_conversation is None:
                    return None

                await Message.record(
                    active_conversation.id, message, session, span=span
                )

                await session.commit()
            except Exception as e:
                await session.rollback()
                span.error(f"Error handling text message: {e}")
                await BOT.reply_to(message, "I'm sorry, I didn't catch that.")
            finally:
                return None


async def register_bot_commands():
    """
    Register the commands with the bot so that they are accessible to the user through the menu
    """
    await BOT.set_my_commands(
        [
            telebot_types.BotCommand(command, description)
            for command, description in BOT_COMMANDS
        ],
        scope=telebot_types.BotCommandScopeDefault(),
    )


async def run():
    LOGGER.info("Starting Bot...")
    try:
        # Get the bot's user name and set the perosna name
        bot_info = await BOT.get_me()
        LOGGER.info(f"Bot started: {bot_info.username}")
        set_bot_name(bot_info.username)
        await register_bot_commands()
        await BOT.polling()
    except Exception as e:
        LOGGER.error(f"An unexpected error occurred: {e}")
    finally:
        LOGGER.info("Stopping Bot...")
        # Close all open connections
        await AGENT.clear_all_chats()


if __name__ == "__main__":
    asyncio.run(run())
