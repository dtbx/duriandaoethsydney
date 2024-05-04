from sqlalchemy import (
    Column,
    Integer,
    Enum,
    String,
    DateTime,
    ForeignKey,
    create_engine,
    select,
    func,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.orm import sessionmaker, relationship, joinedload
from telebot import types as telebot_types
import datetime
import asyncio
from enum import Enum as PyEnum, unique

Base = declarative_base()

# NOTE: it is generally a good idea to make your database schema match your domain model
# At the moment all of our fields are the same, allowing us to interchange telebot types with our database types


class DatabaseError(PyEnum):
    conflict = "conflict"
    not_found = "not_found"
    invalid = "invalid"


class DatabaseException(Exception):
    def __init__(self, db_error: DatabaseError, message: str):
        self.message = message
        self.db_error = db_error

    def __str__(self):
        return f"{self.message}"

    @staticmethod
    def from_sqlalchemy_error(e):
        # TODO: better type checking here
        # If this is not an instance of a sqlalchemy error, just pass it through
        if not isinstance(e, Exception):
            return e
        if "FOREIGN KEY constraint failed" in str(e):
            return DatabaseException(DatabaseError.invalid, str(e))
        if "UNIQUE constraint failed" in str(e):
            return DatabaseException(DatabaseError.conflict, str(e))
        if "No row was found for one" in str(e):
            return DatabaseException(DatabaseError.not_found, str(e))
        if "CHECK constraint failed" in str(e):
            return DatabaseException(DatabaseError.invalid, str(e))
        # Otherwise just pass through the error
        return e


class User(Base):
    __tablename__ = "users"

    # The telegram user ID
    id = Column(Integer, primary_key=True)

    username = Column(String, nullable=True)

    first_name = Column(String)
    last_name = Column(String)

    language_code = Column(String)

    # We'll setup linking back to messages for the purpose of
    #  linking through replies
    messages = relationship("Message", back_populates="from_user")

    @staticmethod
    async def create(user, session, span=None):
        try:
            user = User(
                id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                language_code=user.language_code,
            )
            session.add(user)

            # Flush so the user is created and we can get the ID
            #  within the same session
            await session.flush()

            if span:
                span.info(f"User::create(): Created user for user_id: {user.id}")
            return user
        except Exception as e:
            if span:
                span.error(f"User::create(): Error creating user: {e}")
            e = DatabaseException.from_sqlalchemy_error(e)
            raise e

    @staticmethod
    async def read(user_id, session, span=None):
        try:
            user = await session.execute(select(User).filter(User.id == user_id))
            user = user.scalars().first()
            return user
        except Exception as e:
            if span:
                span.error(f"AsyncDatabase::read_user(): Error reading user: {e}")
            e = DatabaseException.from_sqlalchemy_error(e)
            raise e


class Chat(Base):
    __tablename__ = "chats"

    # The telegram chat ID
    id = Column(Integer, primary_key=True, nullable=False)

    # DAO configuration
    dao_address = Column(String, nullable=False)
    chain_id = Column(Integer, nullable=False)

    # TODO: Fill in info on the chat for managing DAOs
    # You can include permissions, prompts, contract addresses etc

    conversations = relationship("Conversation", back_populates="chat")

    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    # Contracts and Chains should be unique together
    __table_args__ = (UniqueConstraint("dao_address", "chain_id"),)

    @staticmethod
    async def create(chat_id, dao_address, chain_id, session, span=None):
        """
        Create a new chat.
        """
        try:
            chat = Chat(
                id=chat_id,
                dao_address=dao_address,
                chain_id=chain_id,
                created_at=datetime.datetime.now(),
                updated_at=datetime.datetime.now(),
            )
            session.add(chat)

            # Flush so the chat is created and we can get the ID
            # within the same session
            await session.flush()

            if span:
                span.info(f"Chat::create(): Created chat for chat_id: {chat_id}")

            return chat
        except Exception as e:
            if span:
                span.error(f"Chat::create(): Error creating chat: {e}")
            e = DatabaseException.from_sqlalchemy_error(e)
            raise e

    @staticmethod
    async def read(chat_id, session, span=None):
        try:
            chat = await session.execute(select(Chat).filter(Chat.id == chat_id))
            chat = chat.scalars().first()
            return chat
        except Exception as e:
            if span:
                span.error(f"Chat::read(): Error reading chat: {e}")
            e = DatabaseException.from_sqlalchemy_error(e)
            raise e

    @staticmethod
    async def read_by_dao(dao_address, chain_id, session, span=None):
        try:
            chat = await session.execute(
                select(Chat).filter(
                    Chat.dao_address == dao_address, Chat.chain_id == chain_id
                )
            )
            chat = chat.scalars().first()
            return chat
        except Exception as e:
            if span:
                span.error(f"Chat::read_by_dao(): Error reading chat: {e}")
            e = DatabaseException.from_sqlalchemy_error(e)
            raise e


class SummaryState(PyEnum):
    pending = "pending"
    complete = "complete"
    failed = "failed"


class Summary(Base):
    __tablename__ = "summaries"

    # Unqiue Id of the Summary
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)

    # Conversation this summary belongs too
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    conversation = relationship("Conversation", back_populates="summaries")

    # How many messages to read into the conversation
    #  This represents when /summary is called
    # This is just how many messages were in the conversation
    #  when /summary was called
    # Keeping track of this allows us to regenerate later
    # TODO: this should probably be a unique constraint!
    # Since we can only have one summary per point in a conversation
    #  It's redundant to have multiple summaries for the same point
    #   This is fine for now, but we should probably enforce this
    message_count = Column(Integer, nullable=False)

    # The state of the summary -- we will update this as we generate
    # ['pending', 'complete', 'failed']
    state = Column(Enum(SummaryState))

    # The output of the summary from the first `message_count`
    # nmessages in the conversation
    text = Column(String, nullable=True)

    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    # Unique constraint on the ID and chat ID
    # __table_args__ = (
    #    UniqueConstraint(
    #        "conversation_id", "message_count", name="uix_conversation_id_message_count"
    #    ),
    # )

    @staticmethod
    async def create(conversation_id, session, span=None):
        """
        Create a record of a Summary of the active conversation in a chat.
        Only succeed if there is an active converation.
        If there is not an active conversation, just return.

        Returns
        - the summary if the summary was successfully created, otherwise None
        Exceptions:
        - If there is an error creating the summary
        """
        try:
            # Get the message count
            message_count = await session.execute(
                select(func.count()).select_from(Message)
            )
            message_count = message_count.scalar()

            summary = Summary(
                conversation_id=conversation_id,
                message_count=message_count,
                state=SummaryState.pending,
                created_at=datetime.datetime.now(),
                updated_at=datetime.datetime.now(),
            )
            session.add(summary)

            await session.flush()

            if span:
                span.info(f"Summary::create() - Created summary: {summary.id}")

            return summary
        except Exception as e:
            if span:
                span.error(f"Summary::create() - Error creating summary: {e}")
            e = DatabaseException.from_sqlalchemy_error(e)
            raise e

    @staticmethod
    async def mark(summary_id, text, state, session, span=None):
        """
        Mark a summary as either complete or failed, with the given text

        summary_id: the id of the summary we are marking
        text: the text to associate
        state: the state to mark the summary as
        session: the session to use for the transaction
        span=None: The span to use for tracing, If None, no tracing is done

        Returns
        - nothin
        Exceptions:
        - If there is an error marking the summary, Or if the summary does not exist
        """

        try:
            # Check if there is an active conversation
            summary = await session.execute(
                select(Summary).filter(
                    Summary.id == summary_id,
                )
            )
            summary = summary.scalars().first()

            # This should never happen
            if not summary:
                raise Exception("summary does not exist")

            summary.text = text
            summary.state = str(state)
            summary.updated_at = datetime.datetime.now()

            await session.flush()

            return
        except Exception as e:
            if span:
                span.error(f"Summary::mark() - Error marking summary: {e}")
            e = DatabaseException.from_sqlalchemy_error(e)
            raise e


class ConversationState(PyEnum):
    active = "active"
    inactive = "inactive"
    complete = "complete"
    cancelled = "cancelled"


class Conversation(Base):
    __tablename__ = "conversations"

    # id and chat_id form a compound primary key
    # Unique id for the Conversation
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)

    # Id of the chat the conversation belongs to
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    chat = relationship("Chat", back_populates="conversations")

    # The stated agenda of the conversation
    # This is the agenda that was set when the conversation was started
    agenda = Column(String, nullable=True)

    # ['active', 'inactive', 'complete', 'cancelled']
    state = Column(Enum(ConversationState))

    # This tracks the hash to which the conversation transcript is pushed
    #  to IPFS. If this is null, then the conversation has not been pushed
    ipfs_hash = Column(String, nullable=True)

    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    summaries = relationship("Summary", back_populates="conversation")
    messages = relationship("Message", backref="conversation")

    @staticmethod
    async def active(chat_id, session, span=None):
        """
        Get the active conversation of a chat, or none if there is no such conversations

        """

        try:
            conversation = await session.execute(
                select(Conversation).filter(
                    Conversation.chat_id == chat_id, Conversation.state == "active"
                )
            )
            conversation = conversation.scalars().first()

            return conversation
        except Exception as e:
            if span:
                span.error(
                    f"Conversation::active(): Error getting active conversation: {e}"
                )
            e = DatabaseException.from_sqlalchemy_error(e)
            raise e

    @staticmethod
    async def create(chat_id, agenda, session, span=None):
        """
        Create a new conversation. If there is already an active conversation, return None

        chat_id: The chat ID to start the conversation with
        agenda: The agenda for the conversation
        span: The span to use for tracing. If None, no tracing is done

        Returns:
        - The conversation if the conversation was successfully started. None otherwise
        Exceptions:
        - If there is an error creating the conversation
        """
        try:
            # Check if there is an active conversation
            # If there is, return None

            active_conversation = await Conversation.active(chat_id, session, span)
            if active_conversation:
                return None
            new_conversation = Conversation(
                chat_id=chat_id,
                agenda=agenda,
                state="active",
                created_at=datetime.datetime.now(),
                updated_at=datetime.datetime.now(),
            )

            session.add(new_conversation)

            # Flush so the conversation is created and we can get the ID
            # within the same session
            await session.flush()

            if span:
                span.info(
                    f"Conversation::create(): Starting new conversation for chat {chat_id} | conversation_id: {new_conversation.id}"
                )

            return new_conversation
        except Exception as e:
            if span:
                span.error(f"Conversation::create(): Error creating conversation: {e}")
            e = DatabaseException.from_sqlalchemy_error(e)
            raise e

    @staticmethod
    async def read(chat_id, conversation_id, session, span=None):
        try:
            conversation = await session.execute(
                select(Conversation).filter(
                    Conversation.id == conversation_id,
                    Conversation.chat_id == chat_id,
                )
            )
            conversation = conversation.scalars().first()
            return conversation
        except Exception as e:
            if span:
                span.error(f"Conversation::read(): Error getting conversation: {e}")
            e = DatabaseException.from_sqlalchemy_error(e)
            raise e

    @staticmethod
    async def read_pushed(chat_id, session, span=None):
        try:
            conversations = await session.execute(
                select(Conversation).filter(
                    Conversation.chat_id == chat_id,
                    Conversation.state == "complete",
                    Conversation.ipfs_hash != None,
                )
            )
            conversations = conversations.scalars().all()
            return conversations
        except Exception as e:
            if span:
                span.error(
                    f"Conversation::read_dao_transcripts(): Error getting conversations: {e}"
                )
            e = DatabaseException.from_sqlalchemy_error(e)
            raise e

    @staticmethod
    async def read_by_ipfs_hash(ipfs_hash, session, span=None):
        try:
            conversation = await session.execute(
                select(Conversation).filter(
                    Conversation.ipfs_hash == ipfs_hash,
                )
            )
            conversation = conversation.scalars().first()
            return conversation
        except Exception as e:
            if span:
                span.error(
                    f"Conversation::read_dao_transcripts(): Error getting conversations: {e}"
                )
            e = DatabaseException.from_sqlalchemy_error(e)
            raise e

    @staticmethod
    async def read_all(chat_id, session, span=None):
        try:
            conversations = await session.execute(
                select(Conversation).filter(Conversation.chat_id == chat_id)
            )
            conversations = conversations.scalars().all()
            return conversations
        except Exception as e:
            if span:
                span.error(
                    f"Conversation::read_all(): Error getting conversations: {e}"
                )
            e = DatabaseException.from_sqlalchemy_error(e)
            raise e

    @staticmethod
    async def enter(chat_id, conversation_id, session, span=None):
        try:
            conversation = await Conversation.read(
                chat_id, conversation_id, session, span
            )
            if not conversation:
                return None
            conversation.state = "active"
            conversation.updated_at = datetime.datetime.now()
            await session.flush()
            return conversation
        except Exception as e:
            if span:
                span.error(f"Conversation::enter() - Error entering conversation: {e}")
            e = DatabaseException.from_sqlalchemy_error(e)
            raise e

    @staticmethod
    async def update_state(chat_id, state, session, span=None):
        try:
            if state == ConversationState.active:
                raise Exception("Cannot set state to active. Call enter instead")

            conversation = await Conversation.active(chat_id, session, span)
            if not conversation:
                return None
            conversation.state = state
            conversation.updated_at = datetime.datetime.now()
            await session.flush()
            return conversation
        except Exception as e:
            if span:
                span.error(
                    f"Conversation::update_state() - Error updating conversation state: {e}"
                )
            e = DatabaseException.from_sqlalchemy_error(e)
            raise e

    @staticmethod
    async def set_ipfs_hash(conversation_id, ipfs_hash, session, span=None):
        try:
            conversation = await session.execute(
                select(Conversation).filter(
                    Conversation.id == conversation_id,
                    Conversation.state == "complete",
                )
            )
            conversation = conversation.scalars().first()
            conversation.ipfs_hash = ipfs_hash
            conversation.updated_at = datetime.datetime.now()
            await session.flush()
            return conversation
        except Exception as e:
            if span:
                span.error(
                    f"Conversation::set_ipfs_hash() - Error setting conversation hash: {e}"
                )
            e = DatabaseException.from_sqlalchemy_error(e)
            raise e


class Message(Base):
    __tablename__ = "messages"

    # id and the messages chat.id are unique together, as are its id and conversation_id

    # The telegram message ID within the chat
    id = Column(Integer, primary_key=True, nullable=False)
    # The conveursation this message belongs to
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)

    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    from_user = relationship("User", back_populates="messages")

    reply_to_message_id = Column(Integer, ForeignKey("messages.id"), nullable=True)
    reply_to_message = relationship("Message", remote_side=[id], backref="replies")

    text = Column(String)

    timestamp = Column(DateTime)

    __table_args__ = (UniqueConstraint("id", "conversation_id"),)

    @staticmethod
    async def record(
        conversation_id,
        message: telebot_types.Message,
        session,
        reply_to_message_id=None,
        use_edit_date=False,
        span=None,
    ):
        """
        Add a message to the active conversation for the given chat.

        message: The message to add
        reply_to_message_id: The ID of the message that this message is a reply to
        span: The span to use for tracing. If None, no tracing is done
        """

        try:
            user = await User.read(message.from_user.id, session, span)
            if not user:
                user = await User.create(message.from_user, session, span)

            reply_to_id = reply_to_message_id or (
                message.reply_to_message.message_id
                if message.reply_to_message
                else None
            )

            new_message = Message(
                id=message.message_id,
                conversation_id=conversation_id,
                from_user_id=message.from_user.id,
                reply_to_message_id=reply_to_id,
                text=message.text,
                timestamp=datetime.datetime.fromtimestamp(
                    message.edit_date if use_edit_date else message.date
                ),
            )
            session.add(new_message)

            await session.flush()

            if span:
                span.info(
                    f"Message::record(): Added message to conversation {conversation_id}"
                )

            return new_message
        except Exception as e:
            if span:
                span.error(f"Message::record(): Error adding message: {e}")
            raise e

    @staticmethod
    async def read_all(conversation_id, session, limit=None, span=None):
        try:
            base_query = (
                select(Message)
                .options(joinedload(Message.from_user))
                .options(
                    joinedload(Message.reply_to_message).joinedload(Message.from_user)
                )
                .filter(Message.conversation_id == conversation_id)
            )

            if limit:
                base_query = base_query.limit(limit)

            messages = await session.execute(
                base_query.order_by(Message.timestamp.desc())
            )
            messages = messages.scalars().all()

            await session.flush()

            return messages
        except Exception as e:
            if span:
                span.error(f"Message::read_all(): Error reading message: {e}")
            e = DatabaseException.from_sqlalchemy_error(e)
            raise e


# Database Initialization and helpers


# Simple Synchronous Database for setting up the database
class SyncDatabase:
    def __init__(self, database_path):
        database_url = f"sqlite:///{database_path}"
        self.engine = create_engine(database_url)
        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)


class AsyncDatabase:
    def __init__(self, database_path):
        database_url = f"sqlite+aiosqlite:///{database_path}"
        self.engine = create_async_engine(database_url)
        self.AsyncSession = sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )
        # If this is an in-memory database, we need to create the tables
        if database_path == ":memory:":
            asyncio.run(self.create_tables())

    async def create_tables(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def session(self):
        return self.AsyncSession()
