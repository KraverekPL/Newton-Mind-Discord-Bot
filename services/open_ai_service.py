# -*- coding: utf-8 -*-
import json
import logging
import os
import random
import re

import discord
import openai
from discord.ext import commands
from openai import OpenAI


def get_tools():
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_user_activity",
                "description": "Get user's activity",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {
                            "type": "string",
                            "description": "User format <@1234567890> or can be a name."
                        }
                    },
                    "required": ["user_id"]
                }
            }
        }
    ]
    return tools


def get_personality(user_name=None):
    file_path = 'resources/user_personalities.json'
    with open(file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

    random_user = random.choice(data['users'])
    if user_name:
        selected_user = next((user for user in data['users'] if user['nick'].lower() == user_name.lower()), None)
        if selected_user:
            logging.info(f"{selected_user['nick']}'s Personality: {selected_user['personality']}")
            return selected_user['personality']
    else:
        it_expert_personality = ('I want you to act as an IT Expert. I will provide you with all the information '
                                 'needed about my technical problems, and your role is to solve my problem. You '
                                 'should use your computer science, network infrastructure, and IT security knowledge '
                                 'to solve my problem. Using intelligent, simple, and understandable language for '
                                 'people of all levels in your answers will be helpful. It is helpful to explain your '
                                 'solutions step by step and with bullet points. Try to avoid too many technical '
                                 'details, but use them when necessary. I want you to reply with the solution, '
                                 'not write any explanations. My first problem is “my laptop gets an error with a '
                                 'blue screen.”')
        return it_expert_personality


def get_messages(ai_behaviour: str, message_to_ai):
    user_id_pattern = re.compile(r'<@!?1214162287259025428>')  # remove bot id from msg
    cleaned_content = user_id_pattern.sub('', message_to_ai.content.strip())
    user_name = get_user_name_from_id(message_to_ai.author.id)
    prompt = f'Jestem {user_name}.Powiedz mi: {cleaned_content}.'
    messages = [
        {
            "role": "system",
            "content": ai_behaviour
        },
        {
            "role": "user",
            "content": prompt,
        }
    ]
    return messages


def get_user_name_from_id(user_id: int):
    user_names = {
        266316092794863619: 'testname'
    }
    return user_names.get(user_id, 'Cukiereczku')


def get_user_activity(guild_context: discord.Guild, user_id: str):
    user_activity = ''
    if '<@' in user_id or type(user_id) is int:
        user_id = int(user_id.replace('<@', '').replace('>', ''))
        user = guild_context.get_member(int(user_id))
        if user is None or user.activity is None:
            user_activity = get_custom_activity_per_user()
            logging.info('User activity 1: None')
        for activity in user.activities:
            logging.info(f'User activity 2: {user.activity}')
            if isinstance(activity, discord.Spotify):
                user_activity = f'User is listening to {user.activity.title} by {user.activity.artist} on Spotify'
            elif activity.type == discord.ActivityType.playing:
                user_activity = f'User is playing {user.activity.name}'
            elif activity.type == discord.ActivityType.competing:
                user_activity = f'User is playing {user.activity.name}'
            elif activity.type == discord.ActivityType.streaming:
                user_activity = f'User is streaming {user.activity.name}'
            elif activity.type == discord.ActivityType.custom:
                user_activity = f'User is making custom action {user.activity.name}'
            else:
                user_activity = get_custom_activity_per_user()
    else:
        user_activity = get_custom_activity_per_user()
    logging.info(f'User activity 3: {user_activity}')
    return user_activity


def get_custom_activity_per_user():
    file_path = 'resources/user_activities.json'
    with open(file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

    selected_activity = random.choice(data['aktywnosc'])
    activity_type = selected_activity['typ']
    activity_location = random.choice(selected_activity['miejsce'])

    return f"{activity_type} in {activity_location}"


class OpenAIService(commands.Cog):
    def __init__(self, model_ai):
        self.model_ai = model_ai

    open_ai_token = os.getenv('open_ai_token')
    ai_behaviour = get_personality()
    top_p = float(os.getenv('open_ai_top_p'))
    max_tokens = int(os.getenv('open_ai_max_tokens'))
    temperature = float(os.getenv('open_ai_temperature'))

    def gpt_35_turbo_instruct(self, message_to_ai):
        client = OpenAI(self.open_ai_token)
        response = client.completions.create(
            prompt=message_to_ai,
            model=self.model_ai,
            top_p=self.top_p,
            max_tokens=self.max_tokens,
            temperature=self.temperature
        )
        logging.info(f"Response from API OpenAI: {response}")
        logging.info(
            f"Costs: {response.usage.prompt_tokens}+{response.usage.completion_tokens}={response.usage.total_tokens}")
        return response.choices[0].text

    def gpt_35_turbo_0125(self, message):
        openai.api_key = self.open_ai_token
        response = openai.chat.completions.create(
            messages=get_messages(self.ai_behaviour, message),
            model=self.model_ai,
            max_tokens=self.max_tokens,
            tools=get_tools(),
            tool_choice="auto",
        )
        logging.info(f"First response from API OpenAI: {response}")
        logging.info(
            f"Costs (first call): {response.usage.prompt_tokens}+{response.usage.completion_tokens}={response.usage.total_tokens}")

        available_tools = {
            'get_user_activity': get_user_activity
        }

        message_response = response.choices[0].message
        if message_response.tool_calls:
            messages = get_messages(self.ai_behaviour, message)
            messages.append(message_response)
            for tool_call in message_response.tool_calls:
                function_name = tool_call.function.name
                function_to_call = available_tools[function_name]
                function_args = json.loads(tool_call.function.arguments)
                function_args["guild_context"] = message.guild
                function_response = function_to_call(**function_args)
                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": function_response,
                    }
                )
            response = openai.chat.completions.create(
                model=self.model_ai,
                messages=messages,
            )
        llm_response = response.choices[0].message.content
        logging.info(f"Second response from API OpenAI: {response}")
        logging.info(
            f"Costs (second call): {response.usage.prompt_tokens}+{response.usage.completion_tokens}={response.usage.total_tokens}")
        return llm_response

    def chat_with_gpt(self, message):
        # Send a message to the ChatGPT API and get a response
        try:
            max_openai_length = 500
            if len(message.content.strip()) > max_openai_length:
                return None

            response_from_ai = None
            if 'gpt-3.5-turbo-instruct' in self.model_ai:
                response_from_ai = self.gpt_35_turbo_instruct(message)
            elif 'gpt-3.5-turbo-0125' in self.model_ai:
                response_from_ai = self.gpt_35_turbo_0125(message)

            return response_from_ai
        except Exception as e:
            logging.error(f"Error during calling OpenAI API e: {e.with_traceback()}")
