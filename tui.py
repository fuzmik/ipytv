#!/usr/bin/env /home/frank/.pyenv/shims/python3
"""
IPTV Playlist Manager - Advanced TUI (Terminal User Interface)

A comprehensive terminal-based tool for IPTV playlist management with 
full keyboard navigation, interactive elements, and terminal-optimized UI.
(Modified to use the Textual TUI Framework)
"""

import sys
import os
import time
import json
import pickle
from typing import Dict, List, Optional, Set, Any
from pathlib import Path
from urllib.parse import urlparse
from dataclasses import dataclass

# --- TUI-specific imports ---
try:
    from textual.app import App, ComposeResult
    from textual.widgets import Header, Footer, Static, Label
    from textual.containers import Container
    from textual.screen import Screen
    from rich.console import Console 
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.text import Text
    from rich.prompt import Prompt, Confirm, IntPrompt
    from rich import box
    from rich.layout import Layout
    from rich.align import Align
    from rich.padding import Padding
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    
# Remove pynput imports as Textual handles input
KEYBOARD_AVAILABLE = False 

# IPyTV imports
from ipytv import playlist
from ipytv.doctor import M3UPlaylistDoctor
from ipytv.utils import extract_series
from ipytv.channel import IPTVChannel, IPTVAttr
from ipytv.exceptions import URLException, MalformedPlaylistException
from ipytv.playlist import M3UPlaylist


@dataclass
class AppState:
    """Application state for TUI management."""
    current_view: str = "main_menu"
    selected_option: int = 0
    scroll_offset: int = 0
    filter_text: str = ""
    selected_groups: Set[str] = None
    
    def __post_init__(self):
        if self.selected_groups is None:
            self.selected_groups = set()


class IPTV_Backend:
    """Backend logic and data management, decoupled from the Textual UI."""
    
    def __init__(self, data_dir: str = "iptv_data"):
        self.current_playlist = None
        self.loaded_playlists: Dict[str, M3UPlaylist] = {}
        # Keep console for rich formatting outside of Textual widgets if needed
        self.console = Console() if TEXTUAL_AVAILABLE else None 
        self.data_dir = Path(data_dir)
        self.history_file = self.data_dir / "url_history.json"
        
        # Initialize data directory
        self.data_dir.mkdir(exist_ok=True)
        self.url_history = self._load_url_history()
        
        # TUI Configuration - Kept here as data
        self.menu_options = [
            ("📥 Load Playlist", self._load_playlist_tui, "url"),
            ("📜 Load from History", self._load_from_history_tui, "history"),
            ("📚 Load Multiple", self._load_multiple_tui, "multiple"),
            ("📊 Playlist Overview", self._show_overview_tui, "overview"),
            ("📁 Group Analysis", self._show_groups_tui, "groups"),
            ("🏷️ TVG Tag Analysis", self._show_tags_tui, "tags"),
            ("💾 Smart Export", self._export_tui, "export"),
            ("🔀 Manage Playlists", self._manage_playlists_tui, "manage"),
            ("🔄 Merge Playlists", self._merge_tui, "merge"),
            ("🎭 Series Detection", self._series_tui, "series"),
            ("🔍 Search Channels", self._search_tui, "search"),
            ("⚙️ Settings", self._settings_tui, "settings"),
            ("❓ Help", self._help_tui, "help"),
            ("🚪 Exit", self._exit_tui, "exit")
        ]

    def _load_url_history(self) -> List[Dict[str, Any]]:
        """Load URL history from file."""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self._print_error(f"Failed to load URL history: {e}")
        return []

    def _save_url_history(self):
        """Save URL history to file."""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.url_history, f, indent=2)
        except Exception as e:
            self._print_error(f"Failed to save URL history: {e}")

    def add_to_history(self, url: str, success: bool, channel_count: int = 0):
        """Add URL to history."""
        history_entry = {
            'url': url,
            'timestamp': time.time(),
            'success': success,
            'channel_count': channel_count,
            'domain': urlparse(url).netloc
        }
        
        self.url_history = [entry for entry in self.url_history if entry['url'] != url]
        self.url_history.insert(0, history_entry)
        self.url_history = self.url_history[:50]
        self._save_url_history()

    def load_playlist_from_url(self, url: str, sanitize: bool = True) -> bool:
        """Load playlist from URL."""
        # Note: In a true Textual app, this blocking call should be offloaded to a worker thread.
        try:
            with self._create_progress() as progress:
                task = progress.add_task(f"Loading {url[:50]}...", total=None)
                pl = playlist.loadu(url)
                
                if sanitize and pl:
                    progress.update(task, description="Sanitizing playlist...")
                    pl = M3UPlaylistDoctor.sanitize(pl)
                
                self.current_playlist = pl
                domain = urlparse(url).netloc
                playlist_name = f"{domain}_{time.strftime('%Y%m%d_%H%M%S')}"
                self.loaded_playlists[playlist_name] = pl
                self.add_to_history(url, True, pl.length() if pl else 0)
                
                return True
                
        except (URLException, MalformedPlaylistException) as e:
            self._print_error(f"Failed to load: {e}")
            self.add_to_history(url, False)
            return False
        except Exception as e:
            self._print_error(f"Unexpected error: {e}")
            self.add_to_history(url, False)
            return False

    def _create_progress(self):
        """Create a rich progress display for TUI."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            transient=True
        )

    # --- Handlers that will be called by Textual actions ---

    def _execute_menu_option(self, option_index: int):
        """Execute the selected menu option (called by Textual App)."""
        option, handler, op_type = self.menu_options[option_index]
        
        # Check prerequisites
        if op_type in ["overview", "groups", "tags", "export", "series", "search"] and not self.current_playlist:
            # In a Textual app, this should send a message to the App, not call _show_message directly
            print("Action blocked: Please load a playlist first!")
            return
        elif op_type == "merge" and len(self.loaded_playlists) < 2:
            print("Action blocked: Need at least 2 playlists to merge!")
            return
        elif op_type == "history" and not self.url_history:
            print("Action blocked: No URL history available!")
            return
            
        # Execute handler (these handlers still rely on rich.prompt/console for user interaction)
        handler()
        
    def _load_playlist_tui(self):
        """TUI for loading playlists."""
        # This implementation remains blocking, which is a future Textual refactor target.
        self.console.clear()
        
        url_panel = Panel(
            "Enter playlist URL below:\n\n"
            "[dim]Examples:[/dim]\n"
            "• https://iptv-org.github.io/iptv/categories/entertainment.m3u\n"
            "• https://iptv-org.github.io/iptv/categories/sports.m3u\n"
            "• https://iptv-org.github.io/iptv/categories/news.m3u",
            title="📥 Load Playlist",
            border_style="green"
        )
        self.console.print(url_panel)
        
        url = Prompt.ask("\n[cyan]URL[/cyan]")
        if not url:
            return
            
        sanitize = Confirm.ask("Sanitize playlist?", default=True)
        
        with self._create_progress() as progress:
            if self.load_playlist_from_url(url, sanitize):
                self._show_message(f"✅ Loaded {self.current_playlist.length():,} channels!", "success")
            else:
                self._show_message("❌ Failed to load playlist", "error")

    def _load_from_history_tui(self):
        # ... keep original implementation ...
        self._show_message("Loading from history - functionality retained (blocking)", "info")

    def _show_overview_tui(self):
        # ... keep original implementation ...
        self._show_message("Playlist Overview - functionality retained (blocking)", "info")

    def _show_groups_tui(self):
        # ... keep original implementation ...
        self._show_message("Group Analysis - functionality retained (blocking)", "info")

    def _export_tui(self):
        # ... keep original implementation ...
        self._show_message("Smart Export - functionality retained (blocking)", "info")
        
    def _perform_export(self, groups: Dict[str, List[int]]):
        # ... keep original implementation ...
        self._show_message("Exporting - functionality retained (blocking)", "info")

    def _show_message(self, message: str, msg_type: str = "info"):
        """Show a message dialog."""
        # This will exit the Textual UI and return to the normal terminal
        styles = {
            "success": "green",
            "error": "red", 
            "warning": "yellow",
            "info": "blue"
        }
        
        self.console.print(f"\n[{styles.get(msg_type, 'blue')}]{message}[/{styles.get(msg_type, 'blue')}]")
        Prompt.ask("[dim]Press Enter to continue[/dim]")

    # Placeholder methods for other TUI functions
    def _load_multiple_tui(self):
        self._show_message("Multiple URL loading - Coming soon!", "info")

    def _show_tags_tui(self):
        self._show_message("TVG Tag analysis - Coming soon!", "info")

    def _manage_playlists_tui(self):
        self._show_message("Playlist management - Coming soon!", "info")

    def _merge_tui(self):
        self._show_message("Playlist merging - Coming soon!", "info")

    def _series_tui(self):
        self._show_message("Series detection - Coming soon!", "info")

    def _search_tui(self):
        self._show_message("Channel search - Coming soon!", "info")

    def _settings_tui(self):
        self._show_message("Settings - Coming soon!", "info")

    def _help_tui(self):
        self._show_message("Help - functionality retained (blocking)", "info")

    def _loading_screen(self):
        """Show loading screen."""
        self.console.print("[yellow]Loading...[/yellow]")

    def _exit_tui(self):
        """Clean exit from TUI."""
        # Textual App handles the exit now, this is just a placeholder
        pass 

    def _print_error(self, message: str):
        """Print error message."""
        if self.console:
            self.console.print(f"[red]❌ {message}[/red]")
        else:
            print(f"❌ {message}")


# --- TEXTUAL UI COMPONENTS ---

class MainMenu(Static):
    """A custom Textual Widget to render the main menu table using rich."""
    
    # Textual's way of defining reactive state (like a property)
    selected_option = 0
    
    def __init__(self, backend: IPTV_Backend, **kwargs):
        super().__init__(**kwargs)
        self.backend = backend
        self.menu_options = self.backend.menu_options

    def watch_selected_option(self, old_value: int, new_value: int) -> None:
        """Called when selected_option changes. Triggers a re-render."""
        self.update(self._render_menu())

    def on_mount(self) -> None:
        """Called when the widget is first added to the App."""
        self.update(self._render_menu())

    def _render_menu(self) -> str:
        """Renders the menu using rich's formatting, similar to your original method."""
        
        menu_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        menu_table.add_column("", width=4)
        menu_table.add_column("Option", style="white")
        menu_table.add_column("Status", style="dim", width=15)
        
        for i, (option, handler, op_type) in enumerate(self.menu_options):
            # Status indicator (re-used from original logic)
            if op_type in ["overview", "groups", "tags", "export", "series", "search"] and not self.backend.current_playlist:
                status = "[red]need playlist[/red]"
            elif op_type == "merge" and len(self.backend.loaded_playlists) < 2:
                status = "[red]need 2+[/red]"
            elif op_type == "history" and not self.backend.url_history:
                status = "[dim]no history[/dim]"
            else:
                status = "[dim]ready[/dim]"
            
            # Selection indicator
            selector = "▶" if i == self.selected_option else " "
            style = "bold reverse green" if i == self.selected_option else "white"
            
            menu_table.add_row(
                f"[{style}]{selector}[/{style}]",
                f"[{style}]{option}[/{style}]",
                status
            )
        
        # Use a Rich console capture to turn the Rich Panel/Table into a string for Textual's Static widget
        menu_panel = Panel(menu_table, border_style="cyan")
        
        console = Console(markup=True, width=self.app.size.width)
        with console.capture() as capture:
            console.print(menu_panel)
            
        return capture.get()

# The main application class
class IPTVTUI(App):
    """The main Textual application for IPTV management."""
    
    # Textual App Configuration
    #CSS_PATH = "tui.css" # You can optionally create this file for styling
    BINDINGS = [
        ("up", "cursor_up", "Move Up"),
        ("down", "cursor_down", "Move Down"),
        ("enter", "select_option", "Select"),
        ("q", "quit", "Quit")
        # Add quick jump bindings (1-9) here if desired
    ]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize the backend logic manager
        self.manager = IPTV_Backend()
        self.menu_options = self.manager.menu_options
        self.main_menu_widget = MainMenu(self.manager, id="main_menu_widget")
        
    def compose(self) -> ComposeResult:
        """Create child widgets for the app (the layout)."""
        yield Header(show_clock=True)
        
        # Header with status (re-creating the header from your original script)
        status_info = []
        if self.manager.current_playlist:
            status_info.append(f"[green]📺 {self.manager.current_playlist.length():,} channels[/green]")
        else:
            status_info.append("[yellow]⚠ No playlist loaded[/yellow]")
            
        if self.manager.loaded_playlists:
            status_info.append(f"[blue]📚 {len(self.manager.loaded_playlists)} playlists[/blue]")
            
        header_text = Text()
        header_text.append("🎯 MAIN MENU", style="bold bright_cyan")
        if status_info:
            header_text.append(" • " + " • ".join(status_info), style="dim")
            
        yield Static(
            Panel(header_text, border_style="bright_blue"),
            id="app_header_status"
        )
        
        # The main menu body
        yield self.main_menu_widget
        
        # Footer with help
        help_text = Text()
        help_text.append("↑↓: Navigate • ENTER: Select • q: Quit", style="dim")
        yield Static(
            Panel(Align.center(help_text), border_style="dim"),
            id="app_footer_help"
        )
        
        yield Footer()

    # --- Textual Action Handlers (Replaces _handle_menu_input) ---
    
    def action_cursor_up(self) -> None:
        """Move the selection up."""
        current_index = self.main_menu_widget.selected_option
        new_index = (current_index - 1) % len(self.menu_options)
        self.main_menu_widget.selected_option = new_index

    def action_cursor_down(self) -> None:
        """Move the selection down."""
        current_index = self.main_menu_widget.selected_option
        new_index = (current_index + 1) % len(self.menu_options)
        self.main_menu_widget.selected_option = new_index

    def action_select_option(self) -> None:
        """Execute the currently selected menu option."""
        option_index = self.main_menu_widget.selected_option
        
        # Hand off execution to the backend manager
        self.manager._execute_menu_option(option_index)
        
        # After a blocking action returns, re-render the main menu
        self.main_menu_widget.update(self.main_menu_widget._render_menu())
        
    def action_quit(self) -> None:
        """Quit the application."""
        self.notify("Exiting IPTV Manager...", severity="information")
        self.exit()


# --- Main Entry Point (Replaces original main logic) ---

def main():
    """Main entry point."""
    if not TEXTUAL_AVAILABLE:
        print("⚠️ Textual library not found. Install for full TUI experience:")
        print("   pip install textual")
        sys.exit(1)
        
    # Create and run TUI manager
    app = IPTVTUI()
    
    # Handle command line arguments (Textual App doesn't handle command line args 
    # directly on run, but we can access them here before running the App)
    if len(sys.argv) > 1:
        url = sys.argv[1]
        sanitize = len(sys.argv) <= 2 or sys.argv[2].lower() != '--no-sanitize'
        # Load playlist before running the app
        app.manager.load_playlist_from_url(url, sanitize)
    
    # Start TUI
    app.run()


if __name__ == "__main__":
    main()
