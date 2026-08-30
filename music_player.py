import os
import io
import json
import tkinter as tk
from tkinter import ttk, filedialog
import pygame
from mutagen.flac import FLAC
from PIL import Image, ImageTk

CONFIG_FILE = "config.json"
DEFAULT_DIR = r"D:\flac backups"


class MusicPlayer(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Riddy Player")
        self.geometry("1280x720")
        self.minsize(800, 500)
        self.configure(bg="#202020")

        # Initialize Pygame Mixer
        pygame.mixer.init()

        # Audio & UI State
        self.music_dir = self._load_config()
        self.raw_playlist = []  # Flat list of parsed tracks
        self.album_art_cache = {}  # Cache thumbnail images
        self.current_track = None
        self.is_playing = False
        self.is_paused = False
        self.track_length = 0
        self.seek_offset = 0.0  # Tracks absolute position offset in seconds
        self.is_seeking = False  # Prevents progress loop from jumping while dragging slider

        self._setup_ui()
        self._bind_shortcuts()
        self._load_flac_files()
        self._update_progress()

    def _load_config(self):
        """ Loads the last opened folder path from config.json if available """
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    path = data.get("last_dir")
                    if path and os.path.exists(path):
                        return path
            except Exception:
                pass
        return DEFAULT_DIR if os.path.exists(DEFAULT_DIR) else ""

    def _save_config(self, path):
        """ Saves the currently selected directory to config.json """
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump({"last_dir": path}, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def _setup_ui(self):
        # Configure overall app grid weights for window scalability
        self.columnconfigure(0, weight=4, uniform="pane")
        self.columnconfigure(1, weight=5, uniform="pane")
        self.rowconfigure(0, weight=1)

        # Apply dark Windows 11 style
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure(".", background="#202020", foreground="#ffffff", fieldbackground="#2b2b2b")
        style.configure("Treeview", background="#2b2b2b", foreground="#ffffff", fieldbackground="#2b2b2b", rowheight=36)
        style.map("Treeview", background=[('selected', '#0078d4')])

        # ------------------- LEFT PANE: Library & Search -------------------
        left_pane = tk.Frame(self, bg="#202020", highlightbackground="#333333", highlightthickness=1)
        left_pane.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        left_pane.rowconfigure(2, weight=1)
        left_pane.columnconfigure(0, weight=1)

        # Search & Open Folder Header Bar
        search_frame = tk.Frame(left_pane, bg="#202020")
        search_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))

        btn_open = tk.Button(search_frame, text="📁 Open", command=self._select_folder,
                             bg="#3a3a3a", fg="#ffffff", activebackground="#505050", activeforeground="#ffffff",
                             bd=0, font=("Segoe UI", 8, "bold"), padx=6, pady=2)
        btn_open.pack(side="left", padx=(0, 6))

        tk.Label(search_frame, text="🔍", bg="#202020", fg="#aaaaaa", font=("Segoe UI", 10)).pack(side="left",
                                                                                                 padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._filter_library)
        search_entry = tk.Entry(search_frame, textvariable=self.search_var, bg="#2b2b2b", fg="#ffffff",
                                insertbackground="#ffffff", bd=1, relief="solid", font=("Segoe UI", 9))
        search_entry.pack(side="left", fill="x", expand=True)

        self.list_header = tk.Label(left_pane, text="Library (Albums & Cover Art)", font=("Segoe UI", 9, "bold"),
                                    bg="#202020", fg="#888888", anchor="w")
        self.list_header.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 5))

        # Scrollable Treeview
        tree_container = tk.Frame(left_pane, bg="#202020")
        tree_container.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        tree_container.rowconfigure(0, weight=1)
        tree_container.columnconfigure(0, weight=1)

        tree_scroll = ttk.Scrollbar(tree_container)
        tree_scroll.grid(row=0, column=1, sticky="ns")

        self.track_tree = ttk.Treeview(tree_container, columns=("Title", "Artist"), show="tree headings",
                                       yscrollcommand=tree_scroll.set)
        self.track_tree.heading("#0", text="Album / Track")
        self.track_tree.heading("Title", text="Title")
        self.track_tree.heading("Artist", text="Artist")

        self.track_tree.column("#0", width=180, minwidth=120, stretch=True)
        self.track_tree.column("Title", width=130, minwidth=80, stretch=True)
        self.track_tree.column("Artist", width=100, minwidth=60, stretch=True)

        self.track_tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll.config(command=self.track_tree.yview)

        self.track_tree.bind("<Double-1>", self._on_item_double_click)

        # ------------------- RIGHT PANE: Artwork & Info -------------------
        right_pane = tk.Frame(self, bg="#202020")
        right_pane.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        right_pane.rowconfigure(0, weight=3)  # Album Art
        right_pane.rowconfigure(1, weight=2)  # Controls & Technical Info
        right_pane.columnconfigure(0, weight=1)

        # Cover Art Display Area
        art_frame = tk.Frame(right_pane, bg="#1a1a1a", highlightbackground="#333333", highlightthickness=1)
        art_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 5))

        self.art_label = tk.Label(art_frame, text="No Cover Art", bg="#1a1a1a", fg="#666666", font=("Segoe UI", 11))
        self.art_label.pack(fill="both", expand=True)

        # Media Controls & Metadata Area
        controls_frame = tk.Frame(right_pane, bg="#2b2b2b", highlightbackground="#333333", highlightthickness=1)
        controls_frame.grid(row=1, column=0, sticky="nsew", pady=(5, 0))

        # Track Metadata Title / Artist
        self.lbl_title = tk.Label(controls_frame, text="No track selected", font=("Segoe UI", 11, "bold"), bg="#2b2b2b",
                                  fg="#ffffff", anchor="w")
        self.lbl_title.pack(fill="x", padx=15, pady=(8, 0))

        self.lbl_artist = tk.Label(controls_frame, text="Select a song to play", font=("Segoe UI", 9), bg="#2b2b2b",
                                   fg="#aaaaaa", anchor="w")
        self.lbl_artist.pack(fill="x", padx=15, pady=(0, 2))

        # Audio Tech Specs (Frequency, Bitrate, File Type, Channels)
        self.lbl_tech_info = tk.Label(controls_frame, text="Specs: -- kHz | -- kbps | -- | --", font=("Segoe UI", 8),
                                      bg="#2b2b2b", fg="#0078d4", anchor="w")
        self.lbl_tech_info.pack(fill="x", padx=15, pady=(0, 6))

        # Progress Slider & Time Labels
        time_frame = tk.Frame(controls_frame, bg="#2b2b2b")
        time_frame.pack(fill="x", padx=15)

        self.lbl_time_cur = tk.Label(time_frame, text="0:00", font=("Segoe UI", 8), bg="#2b2b2b", fg="#888888")
        self.lbl_time_cur.pack(side="left")

        self.lbl_time_tot = tk.Label(time_frame, text="0:00", font=("Segoe UI", 8), bg="#2b2b2b", fg="#888888")
        self.lbl_time_tot.pack(side="right")

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Scale(controls_frame, from_=0, to=100, variable=self.progress_var, orient="horizontal")
        self.progress_bar.pack(fill="x", padx=15, pady=(0, 5))

        # Seek Bindings for Interactive Scrubber
        self.progress_bar.bind("<Button-1>", self._on_seek_start)
        self.progress_bar.bind("<B1-Motion>", self._on_seeking)
        self.progress_bar.bind("<ButtonRelease-1>", self._on_seek_end)

        # Media Controls & Volume Frame
        bottom_ctrl = tk.Frame(controls_frame, bg="#2b2b2b")
        bottom_ctrl.pack(fill="x", padx=15, pady=5)

        # Center: Buttons
        btn_frame = tk.Frame(bottom_ctrl, bg="#2b2b2b")
        btn_frame.pack(side="left", expand=True)

        btn_style = {"bg": "#3a3a3a", "fg": "#ffffff", "activebackground": "#505050", "activeforeground": "#ffffff",
                     "bd": 0, "width": 4, "font": ("Segoe UI", 11)}

        self.btn_rewind = tk.Button(btn_frame, text="↺", command=self.rewind_track, **btn_style)
        self.btn_rewind.pack(side="left", padx=3)

        self.btn_prev = tk.Button(btn_frame, text="⏮", command=self.prev_track, **btn_style)
        self.btn_prev.pack(side="left", padx=3)

        self.btn_play = tk.Button(btn_frame, text="▶", command=self.toggle_play, **btn_style)
        self.btn_play.pack(side="left", padx=3)

        self.btn_next = tk.Button(btn_frame, text="⏭", command=self.next_track, **btn_style)
        self.btn_next.pack(side="left", padx=3)

        # Right: Volume Control & Percentage Display
        vol_frame = tk.Frame(bottom_ctrl, bg="#2b2b2b")
        vol_frame.pack(side="right")

        tk.Label(vol_frame, text="🔊", bg="#2b2b2b", fg="#aaaaaa", font=("Segoe UI", 9)).pack(side="left", padx=(0, 2))

        self.vol_var = tk.DoubleVar(value=70)
        pygame.mixer.music.set_volume(0.7)

        self.vol_slider = ttk.Scale(vol_frame, from_=0, to=100, variable=self.vol_var, command=self._set_volume,
                                    length=80)
        self.vol_slider.pack(side="left")

        self.lbl_volume_pct = tk.Label(vol_frame, text="70%", font=("Segoe UI", 9), bg="#2b2b2b", fg="#ffffff", width=4,
                                       anchor="w")
        self.lbl_volume_pct.pack(side="left", padx=(5, 0))

    def _bind_shortcuts(self):
        self.bind("<Control-o>", self._volume_down)
        self.bind("<Control-O>", self._volume_down)
        self.bind("<Control-p>", self._volume_up)
        self.bind("<Control-P>", self._volume_up)

    def _select_folder(self):
        selected_path = filedialog.askdirectory(title="Select FLAC Directory", initialdir=self.music_dir or "C:\\")
        if selected_path:
            self.music_dir = selected_path
            self._save_config(selected_path)
            self._load_flac_files()

    def _load_flac_files(self):
        self.raw_playlist.clear()
        self.album_art_cache.clear()

        if not self.music_dir or not os.path.exists(self.music_dir):
            self.lbl_title.config(text="No folder selected")
            self.lbl_artist.config(text="Click '📁 Open' to browse FLAC files")
            self.list_header.config(text="Library (No directory chosen)")
            self._populate_tree([])
            return

        folder_name = os.path.basename(os.path.normpath(self.music_dir)) or self.music_dir
        self.list_header.config(text=f"Library ({folder_name})")

        for root, _, files in os.walk(self.music_dir):
            for file in files:
                if file.lower().endswith(".flac"):
                    full_path = os.path.join(root, file)
                    try:
                        audio = FLAC(full_path)
                        title = audio.get("title", [os.path.splitext(file)[0]])[0]
                        artist = audio.get("artist", ["Unknown Artist"])[0]
                        album = audio.get("album", ["Unknown Album"])[0]
                        length = audio.info.length
                        sample_rate = audio.info.sample_rate
                        bitrate = int(audio.info.bitrate / 1000) if audio.info.bitrate else 0
                        channels = audio.info.channels
                        filesize_mb = round(os.path.getsize(full_path) / (1024 * 1024), 2)
                    except Exception:
                        title = os.path.splitext(file)[0]
                        artist = "Unknown"
                        album = "Unknown Album"
                        length, sample_rate, bitrate, channels, filesize_mb = 0, 0, 0, 0, 0.0

                    self.raw_playlist.append({
                        "path": full_path,
                        "title": title,
                        "artist": artist,
                        "album": album,
                        "length": length,
                        "sample_rate": sample_rate,
                        "bitrate": bitrate,
                        "channels": channels,
                        "size": filesize_mb
                    })

        self._populate_tree(self.raw_playlist)

    def _get_album_thumb(self, track_path):
        try:
            audio = FLAC(track_path)
            if audio.pictures:
                art_data = audio.pictures[0].data
                image = Image.open(io.BytesIO(art_data))
                image.thumbnail((30, 30), Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(image)
        except Exception:
            pass
        return None

    def _populate_tree(self, tracks):
        for item in self.track_tree.get_children():
            self.track_tree.delete(item)

        albums = {}
        for track in tracks:
            alb = track["album"]
            if alb not in albums:
                albums[alb] = []
            albums[alb].append(track)

        for album_name, track_list in sorted(albums.items()):
            first_track_path = track_list[0]["path"]

            if album_name not in self.album_art_cache:
                self.album_art_cache[album_name] = self._get_album_thumb(first_track_path)

            thumb_icon = self.album_art_cache[album_name]

            if thumb_icon:
                album_node = self.track_tree.insert("", "end", text=f"  {album_name}", image=thumb_icon, open=False)
            else:
                album_node = self.track_tree.insert("", "end", text=f"📁  {album_name}", open=False)

            for track in track_list:
                node_id = self.track_tree.insert(album_node, "end", text=f"  {track['title']}",
                                                 values=(track["title"], track["artist"]))
                track["node_id"] = node_id

    def _filter_library(self, *args):
        query = self.search_var.get().lower().strip()
        if not query:
            self._populate_tree(self.raw_playlist)
            return

        filtered = [
            t for t in self.raw_playlist
            if query in t["album"].lower() or query in t["artist"].lower() or query in t["title"].lower()
        ]
        self._populate_tree(filtered)

    def _on_item_double_click(self, event):
        selected_item = self.track_tree.selection()
        if selected_item:
            node_id = selected_item[0]
            for track in self.raw_playlist:
                if track.get("node_id") == node_id:
                    self.play_track(track)
                    break

    def play_track(self, track, start_pos=0.0):
        self.current_track = track
        self.seek_offset = start_pos  # Store original start offset

        pygame.mixer.music.load(track["path"])
        pygame.mixer.music.play(start=start_pos)
        self.is_playing = True
        self.is_paused = False
        self.btn_play.config(text="⏸")

        self.lbl_title.config(text=track["title"])
        self.lbl_artist.config(text=f"{track['artist']} — {track['album']}")

        ch_str = "Stereo" if track["channels"] == 2 else (
            "Mono" if track["channels"] == 1 else f"{track['channels']} Ch")
        spec_text = f"FLAC | {track['sample_rate'] / 1000:.1f} kHz | {track['bitrate']} kbps | {ch_str} | {track['size']} MB"
        self.lbl_tech_info.config(text=spec_text)

        self.track_length = track["length"]
        self.lbl_time_tot.config(text=self._format_time(self.track_length))

        if "node_id" in track:
            self.track_tree.selection_set(track["node_id"])
            self.track_tree.see(track["node_id"])

        self._load_cover_art(track["path"])

    def toggle_play(self):
        if not self.raw_playlist:
            return

        if not self.is_playing and self.current_track is None:
            self.play_track(self.raw_playlist[0])
        elif self.is_paused:
            pygame.mixer.music.unpause()
            self.is_paused = False
            self.is_playing = True
            self.btn_play.config(text="⏸")
        elif self.is_playing:
            pygame.mixer.music.pause()
            self.is_paused = True
            self.is_playing = False
            self.btn_play.config(text="▶")

    def rewind_track(self):
        """ Restarts current song from the beginning """
        if self.current_track:
            self.seek_offset = 0.0
            pygame.mixer.music.play(start=0.0)
            if self.is_paused:
                pygame.mixer.music.pause()
            self.progress_var.set(0)
            self.lbl_time_cur.config(text="0:00")

    def prev_track(self):
        if self.current_track and self.raw_playlist:
            idx = self.raw_playlist.index(self.current_track)
            if idx > 0:
                self.play_track(self.raw_playlist[idx - 1])

    def next_track(self):
        if self.current_track and self.raw_playlist:
            idx = self.raw_playlist.index(self.current_track)
            if idx < len(self.raw_playlist) - 1:
                self.play_track(self.raw_playlist[idx + 1])

    def _set_volume(self, val):
        pct = int(float(val))
        pygame.mixer.music.set_volume(pct / 100.0)
        self.lbl_volume_pct.config(text=f"{pct}%")

    def _volume_down(self, event=None):
        new_val = max(0, self.vol_var.get() - 5)
        self.vol_var.set(new_val)
        self._set_volume(new_val)

    def _volume_up(self, event=None):
        new_val = min(100, self.vol_var.get() + 5)
        self.vol_var.set(new_val)
        self._set_volume(new_val)

    # ------------------- Seeking Logic -------------------
    def _calculate_seek_time(self, event):
        """ Map click/drag position on the scale bar to track seconds """
        width = self.progress_bar.winfo_width()
        if width > 0 and self.track_length > 0:
            click_x = max(0, min(event.x, width))
            target_pct = click_x / width
            return target_pct * self.track_length
        return 0.0

    def _on_seek_start(self, event):
        if self.current_track and self.track_length > 0:
            self.is_seeking = True
            self._on_seeking(event)

    def _on_seeking(self, event):
        if self.is_seeking and self.track_length > 0:
            target_time = self._calculate_seek_time(event)
            pct = (target_time / self.track_length) * 100
            self.progress_var.set(pct)
            self.lbl_time_cur.config(text=self._format_time(target_time))

    def _on_seek_end(self, event):
        if self.is_seeking and self.current_track and self.track_length > 0:
            target_time = self._calculate_seek_time(event)
            self.seek_offset = target_time  # Update target offset

            # Restart playback at target location
            pygame.mixer.music.play(start=target_time)

            if self.is_paused:
                pygame.mixer.music.pause()
            else:
                self.is_playing = True
                self.btn_play.config(text="⏸")

            self.is_seeking = False

    def _load_cover_art(self, file_path):
        try:
            audio = FLAC(file_path)
            if audio.pictures:
                art_data = audio.pictures[0].data
                image = Image.open(io.BytesIO(art_data))
                image.thumbnail((500, 500), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(image)
                self.art_label.config(image=photo, text="")
                self.art_label.image = photo
                return
        except Exception:
            pass

        self.art_label.config(image="", text="No Cover Art Available")

    def _update_progress(self):
        if self.is_playing and not self.is_paused and not self.is_seeking:
            pos_ms = pygame.mixer.music.get_pos()
            if pos_ms != -1:
                # Add the seek offset to Pygame's elapsed timer
                pos_sec = self.seek_offset + (pos_ms / 1000.0)

                if self.track_length > 0:
                    pct = (pos_sec / self.track_length) * 100
                    self.progress_var.set(pct)
                self.lbl_time_cur.config(text=self._format_time(pos_sec))

                if pos_sec >= self.track_length - 0.5 and self.track_length > 0:
                    self.next_track()

        self.after(500, self._update_progress)

    @staticmethod
    def _format_time(seconds):
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}:{secs:02d}"


if __name__ == "__main__":
    app = MusicPlayer()
    app.mainloop()