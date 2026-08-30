# Riddy Player

![Riddy Player Screenshot](https://files.catbox.moe/t662do.png)

A low memory usage, sleek, dark-themed FLAC music player built with Python, Tkinter, Pygame, and Mutagen.

## Features

* **Library View**: Treeview layout that groups tracks by album, complete with embedded thumbnail icons. Albums remain collapsed by default.
* **Cover Art Viewer**: Dynamic artwork display that scales automatically to fit the UI.
* **Technical Metadata**: Shows sample rate, bitrate, file size, and audio channels for FLAC tracks.
* **Persistent Library Directory**: Easily select any music directory using the built-in folder picker. Your last opened directory is automatically saved to `config.json` and restored on startup.
* **Search & Filter**: Real-time filtering by artist, track title, or album name.
* **Volume Control & Shortcuts**: Smooth slider control with real-time percentage display and hotkeys:
  * `Ctrl` + `P`: Increase volume (+5%)
  * `Ctrl` + `O`: Decrease volume (-5%)

---

## Requirements

Ensure you have Python installed, along with the required dependencies:

```bash
pip install pygame mutagen pillow

