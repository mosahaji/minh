import requests
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET
from xml.dom import minidom

print("Starting EPG Generator...")

# ------------------------------------------------------------------
# Calculate 24-hour block (00:00 today -> 00:00 tomorrow)
# ------------------------------------------------------------------
today = datetime.now()
start_of_day = today.replace(hour=0, minute=0, second=0, microsecond=0)
start_of_next_day = start_of_day + timedelta(days=1)

ts_start = str(int(start_of_day.timestamp()))
ts_end = str(int(start_of_next_day.timestamp()))

print(f"Fetching schedule from: {start_of_day} to {start_of_next_day}")

# ------------------------------------------------------------------
# API Request
# ------------------------------------------------------------------
url = "https://epg.aws.playco.com/api/v1.1/epg/category/events"

params = {
    "ts_start": ts_start,
    "ts_end": ts_end,
    "lang": "en",
    "category": "southasian",
    "limit": "2000",
}

headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 26_0_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/148.0.7778.166 Mobile/15E148 Safari/604.1",
    "Accept": "application/json, text/plain, */*",
    "x-geo-country": "AE",
    "sec-fetch-dest": "empty",
}

try:
    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

except requests.RequestException as e:
    print(f"❌ Request failed: {e}")
    exit(1)

print("✅ Successfully downloaded data from API. Building XML...")

try:
    json_data = response.json()
except Exception as e:
    print(f"❌ Failed to parse JSON: {e}")
    exit(1)

# ------------------------------------------------------------------
# Create XMLTV root
# ------------------------------------------------------------------
tv = ET.Element(
    "tv",
    {
        "generator-info-name": "Playco EPG Generator",
        "generator-info-url": "https://epg.aws.playco.com",
    },
)

channels = json_data.get("data", [])

print(f"Found {len(channels)} channels")

# ------------------------------------------------------------------
# CHANNELS
# ------------------------------------------------------------------
for channel in channels:

    channel_id = (
        channel.get("slug")
        or str(channel.get("id"))
        or channel.get("title", "unknown")
    )

    ch_elem = ET.SubElement(tv, "channel", {"id": channel_id})

    display_name = ET.SubElement(ch_elem, "display-name")
    display_name.text = channel.get("title", "Unknown Channel")

    # Channel icon
    images = channel.get("images", [])

    if isinstance(images, list):
        for image in images:
            if isinstance(image, dict):
                icon_url = image.get("url")

                if icon_url:
                    ET.SubElement(
                        ch_elem,
                        "icon",
                        {"src": icon_url}
                    )
                    break

# ------------------------------------------------------------------
# PROGRAMMES
# ------------------------------------------------------------------
programme_count = 0

for channel in channels:

    channel_id = (
        channel.get("slug")
        or str(channel.get("id"))
        or channel.get("title", "unknown")
    )

    events = channel.get("events", [])

    for event in events:

        start_ts = event.get("tsStart")
        end_ts = event.get("tsEnd")

        if not start_ts or not end_ts:
            continue

        # Handle millisecond timestamps
        if start_ts > 9999999999:
            start_ts = start_ts / 1000

        if end_ts > 9999999999:
            end_ts = end_ts / 1000

        try:
            start_time = datetime.fromtimestamp(
                start_ts,
                timezone.utc
            ).strftime("%Y%m%d%H%M%S +0000")

            end_time = datetime.fromtimestamp(
                end_ts,
                timezone.utc
            ).strftime("%Y%m%d%H%M%S +0000")

        except Exception:
            continue

        prog_elem = ET.SubElement(
            tv,
            "programme",
            {
                "start": start_time,
                "stop": end_time,
                "channel": channel_id,
            },
        )

        # Title
        title = ET.SubElement(
            prog_elem,
            "title",
            {"lang": "en"}
        )
        title.text = event.get("title", "No Title")

        # Description
        description = (
            event.get("description")
            or event.get("synopsis")
            or ""
        )

        desc = ET.SubElement(
            prog_elem,
            "desc",
            {"lang": "en"}
        )
        desc.text = description

        # Category
        category = (
            event.get("genre")
            or event.get("category")
        )

        if category:
            cat_elem = ET.SubElement(
                prog_elem,
                "category",
                {"lang": "en"}
            )
            cat_elem.text = str(category)

        # Episode number
        episode = (
            event.get("episodeNumber")
            or event.get("episode")
        )

        if episode:
            ep_elem = ET.SubElement(
                prog_elem,
                "episode-num",
                {"system": "onscreen"}
            )
            ep_elem.text = f"Episode {episode}"

        # Poster image
        event_images = event.get("images", [])

        if isinstance(event_images, list):
            for img in event_images:
                if isinstance(img, dict):
                    poster = img.get("url")
                    if poster:
                        ET.SubElement(
                            prog_elem,
                            "icon",
                            {"src": poster}
                        )
                        break

        programme_count += 1

print(f"Found {programme_count} programmes")

# ------------------------------------------------------------------
# Pretty XML Output
# ------------------------------------------------------------------
xml_bytes = ET.tostring(
    tv,
    encoding="utf-8"
)

pretty_xml = minidom.parseString(
    xml_bytes
).toprettyxml(
    indent="  ",
    encoding="utf-8"
)

output_filename = "starzplay.xml"

with open(output_filename, "wb") as f:
    f.write(pretty_xml)

print()
print("========================================")
print("✅ EPG generation completed")
print(f"📺 Channels   : {len(channels)}")
print(f"📋 Programmes : {programme_count}")
print(f"💾 Saved to   : {output_filename}")
print("========================================")
