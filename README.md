Podcast Combiner

An automated tool for Linux environments that downloads a week's worth of podcast episodes from an RSS feed, combines them into a single size-efficient audio file, and maintains a private RSS feed for personal consumption.

Features

    RSS Feed Integration: Imports a podcast feed to identify and download recent episodes.

    Automated Downloads: Gathers all episodes from the past seven days.

    Efficient Audio Processing: Combines multiple downloaded audio files into a single, size-optimized .m4a file using ffmpeg.

    Full Metadata Embedding: Embeds chapter markers, show notes, and artwork directly into the final audio file.

    Dynamic RSS Feed Generation: Creates a new or appends to an existing RSS feed, adding the new combined episode and automatically removing old episodes and their corresponding files after a configurable period (default: 60 days).

    Flexible Deployment: Designed to be run as a scheduled task (e.g., a cron job) on any Linux server.

Prerequisites

This script requires the following software to be installed on your system:

    Python 3: The script is written in Python 3.

    pip: The Python package installer.

    ffmpeg: A powerful command-line tool for handling video and audio.

Installation

Install the required Python libraries:
Bash

pip install feedparser requests mutagen

Install ffmpeg (example for Debian/Ubuntu):
Bash

sudo apt-get install ffmpeg

Configuration

Before running the script, modify the configuration variables at the top of the podcast_combiner.py file to match your setup.
Python

# ----------------------------------------------------
# Configuration
# ----------------------------------------------------
PODCAST_URL = "https://feeds.simplecast.com/SBbml57i" # The URL of the RSS feed
DAYS_TO_COMBINE = 7                # The number of days of episodes to combine
OUTPUT_FORMAT = "m4a"              # The output format for the combined file
TEMP_DIR = "temp"                  # Temporary directory for episode downloads
OUTPUT_DIR = "output"              # Directory for the final audio and RSS feed
RSS_FEED_FILENAME = "combined_podcast_feed.xml" # The name of the RSS feed file
EPISODE_RETENTION_DAYS = 60        # Number of days to keep episodes in the feed
BASE_URL = "http://127.0.0.1:8080" # The base URL for your local server
# ----------------------------------------------------

Note on BASE_URL: This URL must be the exact address that your podcast player can use to access the files. For a server running on the same device as your player, this is typically 127.0.0.1 and a port number. The script uses this URL to create links in the RSS feed.

Usage

    Save the file: Save the script as podcast_combiner.py.

    Create directories: Ensure the temp and output directories exist in the same location as the script, or let the script create them.

    Run the script: Execute the script from your terminal.
    Bash

python podcast_combiner.py

Automate with cron: For automatic weekly execution, set up a cron job. This example runs the script every Sunday at 3 AM.
Bash

    0 3 * * 0 /usr/bin/python3 /path/to/your/script/podcast_combiner.py

Workflow

    The script runs as a cron job.

    It reads the original podcast RSS feed, identifying all episodes from the last 7 days.

    It downloads each episode to the temp folder.

    It combines the episodes into a single .m4a file in the output folder, embedding all show notes, artwork, and chapter markers.

    It updates the combined_podcast_feed.xml in the same output folder, adding the new episode and removing any that are older than 60 days.

    You refresh the RSS feed in your podcast player (e.g., Podcast Addict) on your local server. It finds the new episode and plays it seamlessly with chapters and notes intact.
