import requests


class DittyDallyMusicClient:
    def __init__(self, dittyDallyMusicEndpoint):
        self._ddallyEndpoint = dittyDallyMusicEndpoint

    def get_spotify_album_by_id(self, spotifyAlbumID):
        response = requests.get(
            f"{self._ddallyEndpoint}", params={"id": spotifyAlbumID}
        )
        response.raise_for_status()
        if response.content:
            return DittyDallyAlbum(response.json())
        raise ValueError("Empty response received from server")


class DittyDallyAlbum:
    def __init__(self, searchResults):
        self._rawResults = searchResults

    def id(self):
        return self._rawResults["id"]

    def title(self):
        return self._rawResults["title"]

    def album_cover(self):
        return self.metadata()["coverArtURL"]

    def artists(self):
        return self._rawResults["artists"]

    def metadata(self):
        return self._rawResults["meta"]

    def release_date(self):
        return self.metadata()["release_date"]
