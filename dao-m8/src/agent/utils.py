import sys
import nltk

from telebot import types as telebot_types

sys.path.append("..")
import database


def calculate_number_of_tokens(line: str):
    """
    Determine the token length of a line of text
    """
    tokens = nltk.word_tokenize(line)
    return len(tokens)


def fmt_msg_user_name(user: database.User | telebot_types.User):
    """
    Determine the appropriate identifier to which associate a user with
    the chat context
    """
    return user.username or ((user.first_name or "") + " " + (user.last_name or ""))
