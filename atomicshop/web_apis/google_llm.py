import os

import google.generativeai as genai


class GoogleLLM:
    def __init__(
            self,
            llm_api_key: str
    ) -> None:
        self.genai = genai

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
            max_output_tokens: int = 4096
    ):
        """
        Function to get the answer to a question by searching Google Custom Console API and processing the content using Gemini API.
        :param search_query:
        :param additional_llm_instructions:
        :param number_of_top_links:
        :param number_of_characters_per_link:
        :param temperature:
        :param max_output_tokens:
        :return:
        """