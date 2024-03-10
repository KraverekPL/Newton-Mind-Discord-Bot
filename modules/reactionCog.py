# -*- coding: utf-8 -*-
import logging
import os
import random

from discord.ext import commands

from services.common import load_resources_from_file, remove_polish_chars
from services.open_ai_service import OpenAIService


async def get_response_from_openai(enable_ai, message, open_ai_model):
    if enable_ai:
        open_ai_service = OpenAIService(open_ai_model)
        response_from_ai = open_ai_service.chat_with_gpt(message)
        if response_from_ai is not None:
            await message.reply(response_from_ai)
            logging.info(f"Response from OpenAi with msg: {message.content.strip()}:{response_from_ai}")
        else:
            await message.reply('Nie wiem,')
            logging.info(f"Message was too long. Skipping API call.")
    else:
        await message.reply('Nie wiem.')
        logging.info(f"OpenAi API is turned off. Sending default message.")


class ReactionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_taunt_response_from_bot(self, message):
        if self.bot.user.mentioned_in(message):
            config_data = load_resources_from_file('bot_scary_responses.json')
            list_of_words = config_data.get("list_of_words", [])
            list_of_responses = config_data.get("list_of_responses", [])

            for word in list_of_words:
                # Check for words in the list, removing Polish characters in-fly
                normalized_message = remove_polish_chars(message.content.lower())
                if word in normalized_message:
                    rng_response_for_scary_taunt = random.choice(list_of_responses)
                    await message.channel.send(rng_response_for_scary_taunt)
                    logging.info(f"Response for scary taunt a bot with {word}:{rng_response_for_scary_taunt}")
                    return True
        return False
    @commands.Cog.listener()
    async def on_message(self, message):
        """Event handler called when a message is received."""
        enable_ai = os.getenv("enabled_ai", 'False').lower() in ('true', '1', 't')
        open_ai_model = os.getenv('open_ai_model')
        # Ignore messages from bot
        if message.author.bot:
            return

        # Check for responses to taunts bot when the bot is mentioned to be silent
        if await self.get_taunt_response_from_bot(message):
            return

        # If the message has content and the bot is mentioned - send it to Open API gateway
        if self.bot.user.mentioned_in(message):
            await get_response_from_openai(enable_ai, message, open_ai_model)


async def setup(bot):
    await bot.add_cog(ReactionCog(bot))
