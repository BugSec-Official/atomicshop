import os
from typing import Literal

import google.generativeai as genai

from . import google_custom_search
from ..wrappers.playwrightw import scenarios
from .. import urls


class GoogleCustomSearchError(Exception):
    pass


class GoogleLLM:
    def __init__(
            self,
            llm_api_key: str,
            search_api_key: str,
            search_engine_id: str
    ) -> None:
        """
        Constructor for the GoogleLLM class.
        :param llm_api_key: str, the API key for the Gemini API.
        :param search_api_key: str, the API key for the Google Custom Search API.
        :param search_engine_id: str, the search engine ID for the Google Custom Search API.
        """

        self.genai = genai
        self.search_api_key: str = search_api_key
        self.search_engine_id: str = search_engine_id

        os.environ["API_KEY"] = llm_api_key
        genai.configure(api_key=os.environ["API_KEY"])

    def get_current_models(
            self,
            full_info: bool = False
    ) -> list:
        """
        Function to get the current models available in the Gemini API

        :param full_info: bool, if True, returns the full information about the models, otherwise only the names for API usage.
        """
        result_list: list = []
        for model in self.genai.list_models():
            if full_info:
                result_list.append(model)
            else:
                result_list.append(model.name)

        return result_list

    def get_answer_online(
            self,
            search_query_or_url: str,
            text_fetch_method: Literal[
                'playwright_text',
                'js_text',
                'playwright_html',
                'js_html',
                'playwright_copypaste'
            ],
            llm_query: str,
            llm_post_instructions: str,
            number_of_top_links: int = 2,
            number_of_characters_per_link: int = 15000,
            temperature: float = 0,
            # max_output_tokens: int = 4096,
            # model_name: str = 'gemini-2.0-flash-thinking-exp-01-21'
            model_name: str = 'models/gemini-2.5-pro-preview-03-25'
    ) -> str:
        """
        Function to get the answer to a question by searching Google Custom Console API and processing the content using Gemini API.

        :param search_query_or_url: string, is checked if it is a URL or a search query.
            Search query: the search query to search on Google Custom Search.
            URL: the URL to fetch content from without using Google Custom Search.
        :param text_fetch_method: string, the method to fetch text from the URL.
            playwright_text: uses native Playwright to fetch text from the URL.
            js_text: uses Playwright and JavaScript evaluation to fetch text from the URL.
            playwright_html: uses native Playwright to fetch HTML from the URL and then parse it to text using beautiful soup.
            js_html: uses Playwright and JavaScript evaluation to fetch HTML from the URL and then parse it to text using beautiful soup.
            playwright_copypaste: uses native Playwright to fetch text from the URL by copying and pasting the text from rendered page using clipboard.
        :param llm_query: string, the question to ask the LLM about the text content that is returned from the search query or the URL.
        :param llm_post_instructions: string, additional instructions to provide to the LLM on the answer it provided after the llm_query.
        :param number_of_top_links: integer, the number of top links to fetch content from.
        :param number_of_characters_per_link: integer, the number of characters to fetch from each link.
        :param temperature: float, the temperature parameter for the LLM.
        :param max_output_tokens: integer, the maximum number of tokens to generate in the LLM response.
        :param model_name: string, the name of the model to use for the LLM.

        :return: string, the answer by LLM to the question.
        """

        # Check if the search query is a URL.
        if urls.is_valid_url(search_query_or_url):
            # Fetch content from the URL
            contents = scenarios.fetch_urls_content_in_threads(
                urls=[search_query_or_url], number_of_characters_per_link=number_of_characters_per_link,
                text_fetch_method=text_fetch_method)
        # If not a URL, Search Google for links related to the query
        else:
            links, search_error = google_custom_search.search_google(
                query=search_query_or_url, api_key=self.search_api_key, search_engine_id=self.search_engine_id)

            if search_error:
                raise GoogleCustomSearchError(f"Error occurred when searching Google: {search_error}")

            # Get only the first X links to not overload the LLM.
            contents = scenarios.fetch_urls_content_in_threads(
                urls=links[:number_of_top_links], number_of_characters_per_link=number_of_characters_per_link,
                text_fetch_method=text_fetch_method)

        combined_content = ""
        for content in contents:
            combined_content += f'{content}\n\n\n\n================================================================'

        final_question = (f'Answer this question: {llm_query}\n\n'
                          f'Follow these instructions: {llm_post_instructions}\n\n'
                          f'Based on these data contents:\n\n'
                          f'{combined_content}')

        # Ask Gemini to process the combined content
        # gemini_response = self.ask_gemini(final_question, temperature, max_output_tokens, model_name)
        gemini_response = self.ask_gemini(final_question, temperature, model_name)
        return gemini_response

    @staticmethod
    def ask_gemini(
            question: str,
            temperature: float,
            # max_output_tokens: int,
            model_name: str = 'gemini-2.0-flash-thinking-exp-01-21'
    ) -> str:
        """
        Function to ask the Gemini API a question and get the response.
        :param question: str, the question to ask the Gemini API.
        :param temperature: float, the temperature parameter for the LLM.
            While 0 is deterministic, higher values can lead to more creative responses.
        :param model_name: str, the name of the model to use for the LLM.

        max_output_tokens: int, the maximum number of tokens to generate in the LLM response.
            UPDATE: Disabled this feature since it gave exceptions in some situations.
            Example:
                  File ".\Lib\site-packages\google\generativeai\types\generation_types.py", line 464, in text
                    parts = self.parts
                            ^^^^^^^^^^
                  File ".\Lib\site-packages\google\generativeai\types\generation_types.py", line 447, in parts
                    raise ValueError(msg)
                ValueError: Invalid operation: The `response.parts` quick accessor requires a single candidate, but but `response.candidates` is empty.


        :return: str, the response from the Gemini API.
        """
        # Model Configuration
        model_config = {
            "temperature": temperature,
            "top_p": 0.99,
            "top_k": 0,
            # "max_output_tokens": max_output_tokens,
        }

        # model = genai.GenerativeModel('gemini-1.5-pro-latest',
        # noinspection PyTypeChecker
        model = genai.GenerativeModel(model_name, generation_config=model_config)
        response = model.generate_content(question)
        return response.text
