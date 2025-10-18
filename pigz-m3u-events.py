from ipytv import playlist

url = "https://raw.githubusercontent.com/pigzillaaa/daddylive/refs/heads/main/daddylive-channels-events.m3u8"

pl = playlist.loadu(url)
regex = r".*\bEVENTS|\b.*"  # This regex will match any words after EVENTS|
new_pl = pl.search(regex, where=["name", "attributes.group-title"], case_sensitive=False)

# Create a new M3UPlaylist object and add the filtered channels
filtered_playlist = playlist.M3UPlaylist()
for ch in new_pl:
    filtered_playlist.append_channels([ch])

# You can now work with the filtered_playlist
# For example, you can print the names of the channels in the filtered playlist:
for ch in filtered_playlist:
    print(ch.name)
