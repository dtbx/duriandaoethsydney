import aiohttp
import time
from enum import Enum

from .utils import calculate_number_of_tokens
from .prompt_manager import PromptManager
from database import Message
from logger import MessageSpan, RequestSpan


class PromptType(Enum):
    summary = "summary"
    proposal = "proposal"


class Agent:
    """
    An agent that's can summarize the outcome of a conversation.
    """

    def __init__(self, agent_config: dict):
        # Instance Configuration
        self.model_name = agent_config["model"]["name"]
        self.model_api_url = agent_config["model"]["api_url"]
        self.model_engine = agent_config["model"]["engine"]

        # Model Parameters
        self.max_completion_tokens = agent_config["model"]["max_completion_tokens"]
        self.max_prompt_tokens = agent_config["model"]["max_prompt_tokens"]
        self.temperature = agent_config["model"]["temperature"]
        self.sampler_order = agent_config["model"]["sampler_order"]
        self.top_p = agent_config["model"]["top_p"]
        self.top_k = agent_config["model"]["top_k"]
        self.stop_sequences = agent_config["prompt_format"]["stop_sequences"]

        # Agent Behavior
        self.max_completion_tries = agent_config["agent"]["max_completion_tries"]

        # Initialize an empty Map to track open context slots on the server
        self.model_conversation_slots = {}
        # Initialize the Prompt Manager
        self.prompt_manager = PromptManager(agent_config)

    # State Helpers

    def name(self):
        """
        Return the name of the chat bot
        """
        return self.prompt_manager.name

    def set_name(self, name: str):
        """
        Set the persona name for the chat bot
        """
        self.prompt_manager.set_name(name)

    async def clear_chat(self, conversation_id: str):
        """
        Clear the chat from the model's available context
        """
        if conversation_id in self.model_conversation_slots:
            session, _ = self.model_conversation_slots[conversation_id]
            await session.close()
            del self.model_conversation_slots[conversation_id]

    async def clear_all_chats(self):
        """
        Close all open sessions
        """
        for session, _ in self.model_conversation_slots.values():
            await session.close()
        self.model_conversation_slots = {}

    # Where the magic happens

    async def build_prompt(
        self,
        messages: list[Message],
        span: MessageSpan,
        prompt_type: PromptType = PromptType.proposal,
    ) -> tuple[str, int]:
        # Keep track of how many tokens we're using
        used_tokens = 0
        token_limit = self.max_prompt_tokens

        # Generate our system prompt
        system_prompt = ""
        system_prompt_tokens = 0
        match prompt_type:
            case PromptType.summary:
                system_prompt, system_prompt_tokens = (
                    self.prompt_manager.summary_system_prompt(token_limit=token_limit)
                )
            case PromptType.proposal:
                system_prompt, system_prompt_tokens = (
                    self.prompt_manager.proposal_system_prompt(token_limit=token_limit)
                )

        # Generate our agent prompt for the model to complete on
        prompt_response, prompt_response_tokens = self.prompt_manager.prompt_response(
            message=None, token_limit=token_limit - system_prompt_tokens
        )

        # Now start filling in the chat log with as many tokens as we can
        basic_prompt_tokens = system_prompt_tokens + prompt_response_tokens
        used_tokens += basic_prompt_tokens
        chat_log_lines = []
        try:
            # Iterate over the messages we've pulled
            for message in messages:
                line = self.prompt_manager.chat_message(message)
                # Calculate the number of tokens this line would use
                additional_tokens = calculate_number_of_tokens(line)

                # Break if this would exceed our token limit before appending to the log
                if used_tokens + additional_tokens > token_limit:
                    span.warn(
                        f"Agent::build_prompt(): exceeded token limit. Used tokens: {used_tokens}, additional tokens: {additional_tokens}, token limit: {token_limit}"
                    )
                    break

                # Update our used tokens count
                used_tokens += additional_tokens

                # Actually append the line to the log
                chat_log_lines.append(line)

            # Now build our prompt in reverse
            chat_log = ""
            for line in reversed(chat_log_lines):
                chat_log = f"{chat_log}{line}"

            return f"{system_prompt}{chat_log}{prompt_response}", used_tokens
        except Exception as e:
            # Log the error, but return the portion of the prompt we've built so far
            span.error(
                f"Agent::build_prompt(): error building prompt: {str(e)}. Returning partial prompt."
            )
            raise e

    async def complete(
        self, prompt: str, conversation_id: int, span: MessageSpan
    ) -> tuple[str, int, bool]:
        """
        Complete on a prompt against our model within a given number of tries.

        Returns a str containing the prompt's completion.
        """

        if conversation_id in self.model_conversation_slots:
            session, slot_id = self.model_conversation_slots[conversation_id]
        else:
            session = aiohttp.ClientSession()
            slot_id = -1

        params = {
            "prompt": prompt,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
        }

        # Update the parameters based on the model engine
        if self.model_engine == "llamacpp":
            params.update(
                {
                    "n_predict": self.max_completion_tokens,
                    # NOTE: for now just set both of these
                    "id_slot": slot_id,
                    "slot_id": slot_id,
                    "typical_p": 1,
                    "tfs_z": 1,
                    "stop": self.stop_sequences,
                    "cache_prompt": True,
                    "use_default_badwordsids": False,
                }
            )
        else:
            raise Exception("Agent::complete(): unsupported model engine")

        max_tries = self.max_completion_tries
        tries = 0
        errors = []
        while tries < max_tries:
            span.debug(
                f"Agent::complete(): attempt: {tries} | slot_id: {slot_id}",
            )
            try:
                async with session.post(self.model_api_url, json=params) as response:
                    if response.status == 200:
                        # Read the response
                        response_data = await response.json()

                        # Get the slot id from the response
                        if "id_slot" in response_data:
                            slot_id = response_data["id_slot"]
                        elif "slot_id" in response_data:
                            slot_id = response_data["slot_id"]
                        self.model_conversation_slots[conversation_id] = (
                            session,
                            slot_id,
                        )

                        # Determine if we're stopped
                        stopped = (
                            response_data["stopped_eos"]
                            or response_data["stopped_word"]
                        )
                        result = response_data["content"]
                        token_count = calculate_number_of_tokens(result)
                        if token_count > self.max_completion_tokens:
                            span.warn("Agent::complete(): Exceeded token limit")
                        return result, token_count, stopped
                    else:
                        raise Exception(
                            f"Agent::complete(): Non 200 status code: {response.status}"
                        )
            except Exception as e:
                span.warn(f"Agent::complete(): Error completing prompt: {str(e)}")
                errors.append(e)
            finally:
                tries += 1
        # If we get here, we've failed to complete the prompt after max_tries
        raise Exception(f"Agent::complete(): Failed to complete prompt: {errors}")

    # TODO: split out the response yielding from rendering the response
    async def yield_response(
        self,
        messages: Message,
        conversation_id: int,
        prompt_type: PromptType,
        span: MessageSpan | RequestSpan,
    ):
        """
        Yield a response from the agent given it's current state and the message it's responding to.

        Yield a tuple of form (response, stopped) where stopped is a boolean indicating whether the response is complete.
        """
        start = time.time()
        span.info("Agent::yield_response()")

        max_completion_tries = self.max_completion_tries

        # Build the prompt
        prompt, used_tokens = await self.build_prompt(messages, span, prompt_type)

        span.info(f"Agent::yield_response(): prompt used tokens: {used_tokens}")
        span.debug("Agent::yield_response(): prompt built: " + prompt)

        try:
            # Keep track of the tokens we've seen out of completion
            completion_tokens = 0
            completion_try = 0
            while completion_try < max_completion_tries:
                # Complete and determine the tokens used
                completion, used_tokens, stopped = await self.complete(
                    prompt, conversation_id, span
                )
                completion_tokens += used_tokens

                span.debug("Agent::yield_response(): completion: " + completion)

                total_time = time.time() - start
                # Log
                # - completion tokens -- how many tokens the model generated
                # - time -- how long we spent
                span.info(
                    f"Agent::yield_response(): completion tokens: {completion_tokens} | time: {total_time}"
                )
                yield completion, stopped
                if stopped:
                    break
                prompt += completion
        except Exception as e:
            raise e
