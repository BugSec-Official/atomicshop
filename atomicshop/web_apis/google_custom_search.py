from typing import Union

from googleapiclient.discovery import build
import googleapiclient.errors


def search_google(
        query: str,
        api_key: str,
        search_engine_id: str
) -> tuple[
        Union[list[str], None],
        str]:
    """
    Function to search Google using Google Custom Search API for links related to a query.
    :param query: string, the search query to search on Google Custom Search.
    :param api_key: string, the API key for the Google Custom Search API.
    :param search_engine_id: string, the search engine ID for the Google Custom Search API.

    :return: tuple(list of strings - the links related to the query, string - the error message if any)
    """

    # noinspection PyTypeChecker
    error: str = None

    try:
        service = build("customsearch", "v1", developerKey=api_key)
        result = service.cse().list(
            q=query,
            cx=search_engine_id,
            # gl="us",  # Country code
            # lr="lang_en",  # Language restriction
            # safe="off",  # Safe search off
            # dateRestrict="m1"  # Restrict results to the last month
        ).execute()
        items = result.get('items', [])
        links = [item['link'] for item in items if 'link' in item]
        return links, error
    except googleapiclient.errors.HttpError as e:
        # In case of rate limit error, return the error message.
        if e.status_code == 429:
            return None, str(e.reason)
        else:
            raise e
