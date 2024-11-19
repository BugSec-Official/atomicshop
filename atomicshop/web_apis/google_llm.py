import os

import google.generativeai as genai

from . import google_custom_search
from ..wrappers.playwrightw import scenarios


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

    def get_current_models(self) -> list[str]:
        """ Function to get the current models available in the Gemini API """
        result_list: list[str] = []
        for model in self.genai.list_models():
            result_list.append(model.name)

        return result_list

    def get_answer_online(
            self,
            search_query: str,
            additional_llm_instructions: str,
            number_of_top_links: int = 2,
            number_of_characters_per_link: int = 15000,
            temperature: float = 0,
            max_output_tokens: int = 4096,
            model_name: str = 'gemini-pro'
    ) -> str:
        """
        Function to get the answer to a question by searching Google Custom Console API and processing the content using Gemini API.

        :param search_query: string, the search query to search on Google Custom Search.
        :param additional_llm_instructions: string, additional instructions to provide to the LLM.
        :param number_of_top_links: integer, the number of top links to fetch content from.
        :param number_of_characters_per_link: integer, the number of characters to fetch from each link.
        :param temperature: float, the temperature parameter for the LLM.
        :param max_output_tokens: integer, the maximum number of tokens to generate in the LLM response.
        :param model_name: string, the name of the model to use for the LLM.

        :return: string, the answer by LLM to the question.
        """

        # Search Google for links related to the query
        links, search_error = google_custom_search.search_google(
            query=search_query, api_key=self.search_api_key, search_engine_id=self.search_engine_id)

        if search_error:
            raise GoogleCustomSearchError(f"Error occurred when searching Google: {search_error}")

        # Get only the first X links to not overload the LLM.
        contents = scenarios.fetch_urls_content_in_threads(links[:number_of_top_links], number_of_characters_per_link)

        combined_content = ""
        for content in contents:
            combined_content += f'{content}\n\n\n\n================================================================'

        final_question = (f'Answer this question: {search_query}\n\n'
                          f'Follow these instructions: {additional_llm_instructions}\n\n'
                          f'Based on these data contents:\n\n'
                          f'{combined_content}')

        # Ask Gemini to process the combined content
        gemini_response = self.ask_gemini(final_question, temperature, max_output_tokens, model_name)
        return gemini_response

    @staticmethod
    def ask_gemini(
            question: str,
            temperature: float,
            max_output_tokens: int,
            model_name: str = 'gemini-pro'
    ) -> str:
        """
        Function to ask the Gemini API a question and get the response.
        :param question: str, the question to ask the Gemini API.
        :param temperature: float, the temperature parameter for the LLM.
            While 0 is deterministic, higher values can lead to more creative responses.
        :param max_output_tokens: int, the maximum number of tokens to generate in the LLM response.
        :param model_name: str, the name of the model to use for the LLM.

        :return: str, the response from the Gemini API.
        """
        # Model Configuration
        model_config = {
            "temperature": temperature,
            "top_p": 0.99,
            "top_k": 0,
            "max_output_tokens": max_output_tokens,
        }

        # model = genai.GenerativeModel('gemini-1.5-pro-latest',
        # noinspection PyTypeChecker
        model = genai.GenerativeModel(model_name, generation_config=model_config)
        response = model.generate_content(question)
        return response.text
