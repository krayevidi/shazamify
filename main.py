import csv
from collections import namedtuple, defaultdict

import ipdb
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
import settings

SpotifyTrack = namedtuple('Track', ['id', 'title', 'artists', 'repr'])

USER_ID = settings.USER_ID
SCOPE = settings.SCOPE
CLIENT_ID = settings.CLIENT_ID
CLIENT_SECRET = settings.CLIENT_SECRET
PLAYLIST_ID = settings.PLAYLIST_ID


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    @classmethod
    def paint(cls, string, color):
        return ''.join([color, string, cls.ENDC])


class ShazamLibraryTrack:
    def __init__(self, title, artist):
        self.title = title
        self.artist = artist

    def __eq__(self, other):
        if not isinstance(other, ShazamLibraryTrack):
            raise NotImplementedError
        return self.title == other.title and self.artist == other.artist

    def __str__(self):
        return f'<ShazamLibraryTrack: {self.get_search_term()}>'

    def get_search_term(self):
        return f'{self.artist} {self.title}'


class ShazamLibrary:
    tracks: [ShazamLibraryTrack]

    def __init__(self, csv_file_path='shazamlibrary.csv'):
        self.tracks = []
        self.csv_file_path = csv_file_path
        self.load_from_csv()

    def load_from_csv(self):
        with open(self.csv_file_path) as csvfile:
            reader = csv.reader(csvfile)

            for row in reader:
                if not row[0].isdigit():
                    continue
                self.add_track(ShazamLibraryTrack(row[2], row[3]))

    def add_track(self, track: ShazamLibraryTrack):
        if track in self.tracks:
            return
        self.tracks.append(track)


class SpotifyPlaylist:
    def __init__(self, playlist_id=PLAYLIST_ID, autoload=True):
        token = spotipy.util.prompt_for_user_token(
            USER_ID,
            scope=SCOPE,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri='https://localhost:8080'
        )
        self.client = spotipy.Spotify(auth=token)
        self.tracks = []
        self.playlist_id = playlist_id

        if autoload:
            self.load()

    def load(self):
        self.tracks = []
        offset = 0
        results = []

        while True:
            response = self.client.playlist_items(
                self.playlist_id,
                offset=offset,
                fields='items.track.id,items.track.name,items.track.artists,total',
                additional_types=['track']
            )

            items = response['items']
            if len(items) == 0:
                break

            results.extend(items)
            offset = offset + len(items)

        for item in results:
            track = self.make_spotify_track_from_raw_item(item)
            self.add_track_local(track)

    def add_track_local(self, track: SpotifyTrack):
        self.tracks.append(track)

    def has_track(self, title, artist):
        for track in self.tracks:
            if title.lower() in track.title.lower() and artist.lower() in map(str.lower, track.artists):
                return True
        return False

    def has_track_with_id(self, track_id):
        for track in self.tracks:
            if track_id == track.id:
                return True
        return False

    def make_spotify_track_from_raw_item(self, item):
        if 'track' in item:
            item = item['track']
        artists = [x['name'] for x in item['artists']]
        representation = f'{", ".join(artists)} {item["name"]}'
        return SpotifyTrack(item['id'], item['name'], artists, representation)

    def search_track(self, term):
        print(f'Searching for: {bcolors.paint(term, bcolors.OKGREEN)}', end=' ')
        results = self.client.search(term)['tracks']
        total = results['total']
        if total == 0:
            print(bcolors.paint('Not found', bcolors.WARNING))
            return
        else:
            print(f'Got {total} result(s)', end=' ')

        item = results['items'][0]
        track = self.make_spotify_track_from_raw_item(item)

        print(bcolors.paint(track.repr, bcolors.OKGREEN))
        return item['id']

    def add_tracks(self, id_list):
        chunk_size = 100
        chunks = [id_list[i:i + chunk_size] for i in range(0, len(id_list), chunk_size)]
        for chunk in chunks:
            self.client.user_playlist_add_tracks(USER_ID, playlist_id=self.playlist_id, tracks=chunk)
        print(f'added {len(id_list)} tracks')

    def remove_duplicates(self):
        print('Removing duplicates...', end=' ')
        self.load()
        result = defaultdict(int)
        for track in self.tracks:
            result[track.id] += 1

        track_ids = [track_id for track_id, count in result.items() if count > 1]
        print(f'{len(track_ids)} item(s) found')
        self.client.playlist_remove_all_occurrences_of_items(self.playlist_id, track_ids)
        self.add_tracks(track_ids)

    def import_from_shazam(library: ShazamLibrary):
        id_set = set()
        skipped = []
        skipped_ids = []
        not_found = []
        for track in library.tracks:
            search_term = track.get_search_term()
            if self.has_track(track.title, track.artist):
                skipped.append(search_term)
                continue

            spotify_track_id = self.search_track(search_term)
            if spotify_track_id:
                if not self.has_track_with_id(spotify_track_id):
                    id_set.add(spotify_track_id)
                else:
                    skipped_ids.append(spotify_track_id)
            else:
                not_found.append(search_term)

        if skipped:
            print('---SKIPPED, ALREADY EXISTS---')
            for item in skipped:
                print(item)

        if not_found:
            print('---NOT FOUND---')
            for item in not_found:
                print(item)

        if id_set:
            self.add_tracks(list(id_set))

        self.remove_duplicates()


def main():
    library = ShazamLibrary()
    playlist = SpotifyPlaylist()
    # playlist.import_from_shazam(library)


if __name__ == '__main__':
    main()
