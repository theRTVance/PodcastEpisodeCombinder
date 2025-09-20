import feedparser
import requests
import os
import re
import subprocess
import json
from datetime import datetime, timedelta
from mutagen.mp4 import MP4, MP4Cover, Chapter
from xml.etree.ElementTree import Element, SubElement, tostring, ElementTree
from xml.dom import minidom

# ----------------------------------------------------
# Configuration
# ----------------------------------------------------
PODCAST_URL = "YOUR FEED HERE"
DAYS_TO_COMBINE = 7
OUTPUT_FORMAT = "Use File Format from RSS Feed. Ex: mp3, M4a, wav" 
TEMP_DIR = "YOUR TEMP FOLDER"
OUTPUT_DIR = "OutputFolder" # New: Directory for final output files
RSS_FEED_FILENAME = "RSS_Name.xml"
EPISODE_RETENTION_DAYS = 30
BASE_URL = "http://127.0.0.1:8080/YOUR_Folder"  # Set this to your phone server's address and port
# ----------------------------------------------------

def sanitize_filename(name):
    return re.sub(r'[^a-zA-Z0-9_.]+', '_', name)

def download_file(url, filename, save_path):
    print(f"Downloading {filename}...")
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        full_path = os.path.join(save_path, filename)
        with open(full_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Download complete.")
        return full_path
    except requests.exceptions.RequestException as e:
        print(f"Failed to download {url}: {e}")
        return None

def get_audio_info(file_path):
    try:
        command = ['ffprobe', '-v', 'error', '-of', 'json', '-show_streams', file_path]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        data = result.stdout
        streams = [s for s in json.loads(data)['streams'] if s['codec_type'] == 'audio']
        if not streams:
            print(f"No audio stream found in {file_path}")
            return None, None
        
        audio_stream = streams[0]
        bitrate = int(audio_stream.get('bit_rate', 0))
        sample_rate = int(audio_stream.get('sample_rate', 0))
        return bitrate, sample_rate
    except (subprocess.CalledProcessError, KeyError, IndexError, ValueError) as e:
        print(f"Could not get audio info for {file_path}: {e}")
        return None, None

def get_file_duration(file_path):
    try:
        command = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', file_path]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        duration = float(data['format']['duration'])
        return duration
    except (subprocess.CalledProcessError, KeyError, IndexError, ValueError) as e:
        print(f"Could not get duration for {file_path}: {e}")
        return 0

def parse_ffmpeg_output(line):
    """
    Parses a line of FFmpeg output to find and return the current time.
    """
    time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2})\.\d{2}', line)
    if time_match:
        hours = int(time_match.group(1))
        minutes = int(time_match.group(2))
        seconds = int(time_match.group(3))
        return hours * 3600 + minutes * 60 + seconds
    return None
def combine_audio_files(file_list, output_path, total_duration):
    with open("filelist.txt", "w") as f:
        for file in file_list:
            f.write(f"file '{os.path.abspath(file)}'\n")

    print("Combining audio files without re-encoding...")
    command = [
        'ffmpeg',
        '-f', 'concat',
        '-safe', '0',
        '-i', 'filelist.txt',
        '-c', 'copy',
        '-threads', '4',
        '-y',
        output_path
    ]

    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

        for line in process.stdout:
            current_time = parse_ffmpeg_output(line)
            if current_time is not None:
                if total_duration > 0:
                    percentage = (current_time / total_duration) * 100
                    time_remaining = total_duration - current_time
                    time_rem_str = str(timedelta(seconds=round(time_remaining)))
                    print(f"Progress: {percentage:.1f}% - Time Remaining: {time_rem_str}", end='\r')
        print("\nCombination successful.")

        process.wait()
        os.remove("filelist.txt")
        return output_path
    except Exception as e:
        print("FFmpeg error:")
        print(e)
        os.remove("filelist.txt")
        return None

def main():
    print("Parsing RSS feed...")
    try:
        feed = feedparser.parse(PODCAST_URL)
        if feed.bozo:
            print(f"Feed is malformed. Error details: {feed.bozo_exception}")
            return
    except Exception as e:
        print(f"Error parsing feed: {e}")
        return

    print("Filtering episodes...")
    today = datetime.now()
    seven_days_ago = today - timedelta(days=DAYS_TO_COMBINE)
    
    episodes_to_combine = []
    
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    for entry in feed.entries:
        if 'published_parsed' in entry:
            pub_date = datetime.fromtimestamp(datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z").timestamp())
            if pub_date >= seven_days_ago:
                episodes_to_combine.append(entry)
                
    if not episodes_to_combine:
        print("No episodes found in the last 7 days. Exiting.")
        return

    episodes_to_combine.sort(key=lambda x: datetime.fromtimestamp(datetime.strptime(x.published, "%a, %d %b %Y %H:%M:%S %z").timestamp()))
    
    downloaded_files = []
    bitrates = []
    sample_rates = []
    episode_titles = []
    episode_show_notes = []
    
    print(f"Found {len(episodes_to_combine)} episodes to combine.")
    for entry in episodes_to_combine:
        filename = sanitize_filename(f"{entry.title}.mp3")
        filepath = os.path.join(TEMP_DIR, filename)

        if not os.path.exists(filepath):
            # File does not exist, so download it
            filepath = download_file(entry.enclosures[0].href, filename, TEMP_DIR)
        else:
            # File already exists, skip download
            print(f"File '{filename}' already exists. Skipping download.")

        if filepath and os.path.exists(filepath):
            downloaded_files.append(filepath)
            episode_titles.append(entry.title)
            
            show_notes = entry.get('summary', entry.get('description', 'No show notes available.'))
            episode_show_notes.append(f"{entry.title}\n{show_notes}\n\n")

            bitrate, sample_rate = get_audio_info(filepath)
            if bitrate and sample_rate:
                bitrates.append(bitrate)
                sample_rates.append(sample_rate)
        else:
            print(f"File not found for episode '{entry.title}'. Skipping.")

    if not downloaded_files:
        print("No files were found in the temp directory. Exiting.")
        return
        
    target_bitrate = min(bitrates) if bitrates else 128
    target_sample_rate = min(sample_rates) if sample_rates else 44100
    
    print(f"Target Bitrate: {target_bitrate} kbps")
    print(f"Target Sample Rate: {target_sample_rate} Hz")
    
    first_title = episode_titles[0]
    last_title = episode_titles[-1]
    
    combined_name = sanitize_filename(f"{first_title}-{last_title}")
    combined_filename = f"{combined_name}.{OUTPUT_FORMAT}"
    final_output_path = os.path.join(OUTPUT_DIR, combined_filename)
    
    # Calculate total duration before combining
    total_duration = sum(get_file_duration(f) for f in downloaded_files)
    
    combined_audio_path = combine_audio_files(downloaded_files, final_output_path, total_duration)
    
    if combined_audio_path:
        try:
            audio = MP4(combined_audio_path)
            audio['\xa9nam'] = combined_name
            audio['\xa9ART'] = feed.feed.author
            audio['desc'] = "".join(episode_show_notes)
            
            if 'image' in episodes_to_combine[0]:
                image_url = episodes_to_combine[0].image['href']
                print("Adding artwork to the combined file...")
                img_data = requests.get(image_url).content
                audio["covr"] = [MP4Cover(img_data, MP4Cover.FORMAT_JPEG)]
            
            audio.save()
            print("Metadata added successfully.")
            
        except Exception as e:
            print(f"Error adding metadata: {e}")

        rss_path = os.path.join(OUTPUT_DIR, RSS_FEED_FILENAME)
        
        if os.path.exists(rss_path):
            print("Existing RSS feed found. Appending new episode...")
            tree = ElementTree(file=rss_path)
            root = tree.getroot()
            channel = root.find('channel')
        else:
            print("No existing RSS feed found. Creating a new one...")
            root = Element('rss', {'version': '2.0', 'xmlns:itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd'})
            channel = SubElement(root, 'channel')
            feed_info = feed.feed
            SubElement(channel, 'title').text = feed_info.get('title')
            SubElement(channel, 'link').text = feed_info.get('link')
            SubElement(channel, 'description').text = feed_info.get('summary')
            SubElement(channel, 'language').text = feed_info.get('language')
        
        item = Element('item')
        SubElement(item, 'title').text = " -- ".join(episode_titles)
        SubElement(item, 'guid').text = combined_filename
        SubElement(item, 'description').text = "".join(episode_show_notes)
        
        file_size = os.path.getsize(os.path.join(OUTPUT_DIR, combined_filename))
        enclosure_url = f"{BASE_URL}/{combined_filename}"
        SubElement(item, 'enclosure', {
            'url': enclosure_url,
            'length': str(file_size),
            'type': 'audio/mp4'
        })
        
        SubElement(item, 'pubDate').text = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
        
        first_item = channel.find('item')
        if first_item is not None:
            channel.insert(list(channel).index(first_item), item)
        else:
            channel.append(item)
        
        items_to_remove = []
        current_time_utc = datetime.utcnow()
        for episode_item in channel.findall('item'):
            pub_date_str = episode_item.find('pubDate').text
            if pub_date_str:
                pub_date = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S GMT")
                if (current_time_utc - pub_date).days > EPISODE_RETENTION_DAYS:
                    items_to_remove.append(episode_item)
                    
                    enclosure = episode_item.find('enclosure')
                    if enclosure is not None:
                        file_url = enclosure.get('url')
                        filename = os.path.basename(file_url)
                        file_path_to_delete = os.path.join(OUTPUT_DIR, filename)
                        if os.path.exists(file_path_to_delete):
                            os.remove(file_path_to_delete)
                            print(f"Deleted old file: {file_path_to_delete}")
        
        for item_to_remove in items_to_remove:
            channel.remove(item_to_remove)
        
        last_build_date_element = channel.find('lastBuildDate')
        if last_build_date_element is not None:
            last_build_date_element.text = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
        else:
            SubElement(channel, 'lastBuildDate').text = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
            
        xml_str = tostring(root, 'utf-8')
        dom = minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent="    ")
        
        with open(rss_path, "w") as f:
            f.write(pretty_xml)
        print(f"RSS feed updated and saved to {rss_path}")

    # Don't delete temp files for already downloaded podcasts
    for file in os.listdir(TEMP_DIR):
        if file not in [os.path.basename(f) for f in downloaded_files]:
            os.remove(os.path.join(TEMP_DIR, file))

    if not os.listdir(TEMP_DIR):
        os.rmdir(TEMP_DIR)
        print("Cleanup complete.")
    else:
        print("Cleanup complete, temp directory not empty.")
    
if __name__ == "__main__":
    main()


