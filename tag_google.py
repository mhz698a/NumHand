"""Build and open Google searches for music metadata."""
from urllib.parse import quote_plus
import webbrowser


GOOGLE_SEARCH_BASE_URL = "https://www.google.com/search?q="
VALID_SEARCH_FIELDS = {"filename", "title_artist"}
VALID_QUALIFIERS = {None, "lyrics", "release date"}


def build_song_search_query(
    filename="",
    title="",
    artist="",
    search_by="filename",
    qualifier=None,
):
    """Build a Google query from a filename or a title/artist pair."""
    if search_by not in VALID_SEARCH_FIELDS:
        raise ValueError(f"Unsupported song search field: {search_by!r}")
    if qualifier not in VALID_QUALIFIERS:
        raise ValueError(f"Unsupported search qualifier: {qualifier!r}")

    if search_by == "filename":
        base_query = str(filename or "").strip()
    else:
        # Do not leave a dangling separator when one metadata field is missing.
        base_query = " - ".join(
            part.strip()
            for part in (str(title or ""), str(artist or ""))
            if part.strip()
        )

    if not base_query:
        return ""

    return " ".join(part for part in (base_query, qualifier) if part).strip()


def build_google_search_url(query):
    """Encode a query for the Google Search URL."""
    query = str(query or "").strip()
    if not query:
        raise ValueError("A non-empty search query is required.")
    return f"{GOOGLE_SEARCH_BASE_URL}{quote_plus(query)}"


def open_song_search(
    filename="",
    title="",
    artist="",
    search_by="filename",
    qualifier=None,
):
    """Open the requested song search in the user's default browser.

    Returns the opened URL, or None when the available metadata is empty.
    """
    query = build_song_search_query(
        filename=filename,
        title=title,
        artist=artist,
        search_by=search_by,
        qualifier=qualifier,
    )
    if not query:
        return None

    url = build_google_search_url(query)
    webbrowser.open(url, new=2)
    return url
