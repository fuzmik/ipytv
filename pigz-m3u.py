from ipytv import playlist

url = "https://raw.githubusercontent.com/pigzillaaa/daddylive/refs/heads/main/daddylive-channels-events.m3u8"

pl = playlist.loadu(url)
regex = r".*\bEVENTS|\b.*"  # This regex will match any words after EVENTS|
new_pl = pl.search(regex, where=["name", "attributes.group-title"], case_sensitive=False)
for ch in new_pl:
    print(f'group: {ch.attributes["group-title"]}, channel: {ch.name}')
