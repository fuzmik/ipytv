#!/usr/bin/env /home/frank/.pyenv/shims/python3
"""
IPTV Playlist Manager - Advanced TUI (Terminal User Interface)

A comprehensive terminal-based tool for IPTV playlist management with 
full keyboard navigation, interactive elements, and terminal-optimized UI.
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

# TUI-specific imports
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.text import Text
    from rich.prompt import Prompt, Confirm, IntPrompt
    from rich import box
    from rich.columns import Columns
    from rich.layout import Layout
    from rich.live import Live
    from rich.align import Align
    from rich.padding import Padding
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

try:
    from pynput import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
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


class TUI_IPTV_Manager:
    """Advanced TUI for IPTV playlist management."""
    
    def __init__(self, data_dir: str = "iptv_data"):
        self.current_playlist = None
        self.loaded_playlists: Dict[str, M3UPlaylist] = {}
        self.console = Console() if RICH_AVAILABLE else None
        self.data_dir = Path(data_dir)
        self.history_file = self.data_dir / "url_history.json"
        self.state = AppState()
        
        # Initialize data directory
        self.data_dir.mkdir(exist_ok=True)
        self.url_history = self._load_url_history()
        
        # TUI Configuration
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
        """Create a progress display for TUI."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            transient=True
        )

    def run(self):
        """Main TUI event loop."""
        self._show_welcome()
        
        try:
            while True:
                if self.state.current_view == "main_menu":
                    self._main_menu_tui()
                elif self.state.current_view == "loading":
                    self._loading_screen()
                else:
                    # Handle other views
                    self.state.current_view = "main_menu"
                    
        except KeyboardInterrupt:
            self._exit_tui()

    def _show_welcome(self):
        """Display welcome screen."""
        if not RICH_AVAILABLE:
            print("🎬 IPTV Playlist Manager - TUI Mode")
            print("Use number keys to navigate, 'q' to quit")
            return
            
        welcome_text = Text()
        welcome_text.append("🎬 IPTV PLAYLIST MANAGER\n", style="bold bright_magenta")
        welcome_text.append("Terminal User Interface\n", style="bold cyan")
        welcome_text.append("\n")
        welcome_text.append("Navigate with: ", style="dim")
        welcome_text.append("↑↓", style="bold yellow")
        welcome_text.append(" keys • Select with: ", style="dim")
        welcome_text.append("ENTER", style="bold green")
        welcome_text.append("\nQuick jump: ", style="dim")
        welcome_text.append("1-9", style="bold yellow")
        welcome_text.append(" • Exit: ", style="dim")
        welcome_text.append("q", style="bold red")
        
        welcome_panel = Panel(
            Align.center(welcome_text),
            border_style="bright_blue",
            box=box.DOUBLE
        )
        
        self.console.print(welcome_panel)
        self.console.print()

    def _main_menu_tui(self):
        """Interactive main menu with keyboard navigation."""
        if not RICH_AVAILABLE:
            self._fallback_menu()
            return
            
        # Create layout
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )
        
        # Header with status
        status_info = []
        if self.current_playlist:
            status_info.append(f"[green]📺 {self.current_playlist.length():,} channels[/green]")
        else:
            status_info.append("[yellow]⚠ No playlist loaded[/yellow]")
            
        if self.loaded_playlists:
            status_info.append(f"[blue]📚 {len(self.loaded_playlists)} playlists[/blue]")
            
        header_content = Text()
        header_content.append("🎯 MAIN MENU", style="bold bright_cyan")
        if status_info:
            header_content.append(" • " + " • ".join(status_info), style="dim")
            
        layout["header"].update(
            Panel(header_content, border_style="bright_blue")
        )
        
        # Menu body
        menu_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        menu_table.add_column("", width=4)
        menu_table.add_column("Option", style="white")
        menu_table.add_column("Status", style="dim", width=15)
        
        for i, (option, handler, op_type) in enumerate(self.menu_options):
            # Status indicator
            if op_type in ["overview", "groups", "tags", "export", "series", "search"] and not self.current_playlist:
                status = "[red]need playlist[/red]"
            elif op_type == "merge" and len(self.loaded_playlists) < 2:
                status = "[red]need 2+[/red]"
            elif op_type == "history" and not self.url_history:
                status = "[dim]no history[/dim]"
            else:
                status = "[dim]ready[/dim]"
            
            # Selection indicator
            selector = "▶" if i == self.state.selected_option else " "
            style = "bold reverse green" if i == self.state.selected_option else "white"
            
            menu_table.add_row(
                f"[{style}]{selector}[/{style}]",
                f"[{style}]{option}[/{style}]",
                status
            )
        
        layout["body"].update(
            Panel(menu_table, border_style="cyan")
        )
        
        # Footer with help
        help_text = Text()
        help_text.append("↑↓: Navigate • ENTER: Select • 1-9: Quick jump • q: Quit", style="dim")
        layout["footer"].update(
            Panel(Align.center(help_text), border_style="dim")
        )
        
        # Display
        self.console.clear()
        self.console.print(layout)
        
        # Handle input
        self._handle_menu_input()

    def _handle_menu_input(self):
        """Handle keyboard input for menu navigation."""
        try:
            if KEYBOARD_AVAILABLE:
                # Use keyboard library for better input handling
                key = keyboard.read_key()
                if key == "up":
                    self.state.selected_option = (self.state.selected_option - 1) % len(self.menu_options)
                elif key == "down":
                    self.state.selected_option = (self.state.selected_option + 1) % len(self.menu_options)
                elif key == "enter":
                    self._execute_menu_option()
                elif key.isdigit() and 1 <= int(key) <= len(self.menu_options):
                    self.state.selected_option = int(key) - 1
                    self._execute_menu_option()
                elif key == "q":
                    raise KeyboardInterrupt
            else:
                # Fallback to simple input
                choice = input("\nSelect option (number or ↑↓+ENTER): ").strip()
                if choice.isdigit() and 1 <= int(choice) <= len(self.menu_options):
                    self.state.selected_option = int(choice) - 1
                    self._execute_menu_option()
                elif choice == "q":
                    raise KeyboardInterrupt
                elif choice == "":
                    self._execute_menu_option()
                    
        except KeyboardInterrupt:
            self._exit_tui()

    def _execute_menu_option(self):
        """Execute the currently selected menu option."""
        option, handler, op_type = self.menu_options[self.state.selected_option]
        
        # Check prerequisites
        if op_type in ["overview", "groups", "tags", "export", "series", "search"] and not self.current_playlist:
            self._show_message("Please load a playlist first!", "warning")
            return
        elif op_type == "merge" and len(self.loaded_playlists) < 2:
            self._show_message("Need at least 2 playlists to merge!", "warning")
            return
        elif op_type == "history" and not self.url_history:
            self._show_message("No URL history available!", "info")
            return
            
        # Execute handler
        handler()

    def _load_playlist_tui(self):
        """TUI for loading playlists."""
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
        """TUI for loading from history."""
        if not self.url_history:
            self._show_message("No URL history available!", "info")
            return
            
        self.console.clear()
        
        history_table = Table(title="📜 URL History", box=box.ROUNDED)
        history_table.add_column("#", style="white", width=4)
        history_table.add_column("URL", style="cyan")
        history_table.add_column("Channels", style="green", width=10)
        history_table.add_column("Status", style="yellow", width=8)
        
        for i, entry in enumerate(self.url_history[:15]):
            status = "✅" if entry['success'] else "❌"
            url_preview = entry['url'][:50] + "..." if len(entry['url']) > 50 else entry['url']
            
            history_table.add_row(
                str(i + 1),
                url_preview,
                str(entry.get('channel_count', 0)),
                status
            )
        
        self.console.print(Panel(history_table, border_style="blue"))
        
        try:
            choice = IntPrompt.ask(
                "\nSelect URL to load (0 to cancel)",
                choices=[str(i) for i in range(0, len(self.url_history[:15]) + 1)],
                default=0
            )
            
            if choice > 0:
                selected_url = self.url_history[choice - 1]['url']
                sanitize = Confirm.ask("Sanitize playlist?", default=True)
                
                if self.load_playlist_from_url(selected_url, sanitize):
                    self._show_message(f"✅ Loaded from history!", "success")
                    
        except Exception:
            pass  # User cancelled

    def _show_overview_tui(self):
        """TUI for playlist overview."""
        self.console.clear()
        
        pl = self.current_playlist
        stats_table = Table(title="📊 Playlist Statistics", box=box.ROUNDED)
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="white")
        
        stats_table.add_row("Total Channels", f"{pl.length():,}")
        stats_table.add_row("Unique Groups", f"{len(pl.group_by_attribute()):,}")
        stats_table.add_row("Unique URLs", f"{len(pl.group_by_url()):,}")
        
        series_map, _ = extract_series(pl)
        stats_table.add_row("Detected Series", f"{len(series_map):,}")
        stats_table.add_row("Playlist Attributes", f"{len(pl.get_attributes()):,}")
        
        self.console.print(Panel(stats_table, border_style="green"))
        Prompt.ask("\n[dim]Press Enter to continue[/dim]")

    def _show_groups_tui(self):
        """TUI for group analysis."""
        self.console.clear()
        
        groups = self.current_playlist.group_by_attribute()
        sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)
        
        groups_table = Table(title="📁 Top Groups", box=box.ROUNDED)
        groups_table.add_column("Rank", style="white")
        groups_table.add_column("Group Name", style="cyan")
        groups_table.add_column("Channels", style="green")
        groups_table.add_column("Percentage", style="yellow")
        
        total_channels = self.current_playlist.length()
        
        for i, (group_name, channel_indices) in enumerate(sorted_groups[:20]):
            count = len(channel_indices)
            percentage = (count / total_channels) * 100
            display_name = group_name if group_name != self.current_playlist.NO_GROUP_KEY else "[No Group]"
            
            groups_table.add_row(
                str(i + 1),
                display_name,
                f"{count:,}",
                f"{percentage:.1f}%"
            )
        
        self.console.print(Panel(groups_table, border_style="blue"))
        Prompt.ask("\n[dim]Press Enter to continue[/dim]")

    def _export_tui(self):
        """Advanced TUI for group-based exporting."""
        if not self.current_playlist:
            self._show_message("No playlist loaded!", "warning")
            return
            
        self.state.selected_groups.clear()
        groups = self.current_playlist.group_by_attribute()
        group_names = sorted([name for name in groups.keys() if name != self.current_playlist.NO_GROUP_KEY])
        
        if not group_names:
            self._show_message("No groups found in playlist!", "info")
            return
            
        # Multi-page group selection
        current_page = 0
        items_per_page = 20
        
        while True:
            self.console.clear()
            
            # Create multi-column display for groups
            start_idx = current_page * items_per_page
            end_idx = min(start_idx + items_per_page, len(group_names))
            
            selection_table = Table(
                title=f"💾 Select Groups for Export (Page {current_page + 1}/{(len(group_names) + items_per_page - 1) // items_per_page})",
                box=box.ROUNDED
            )
            selection_table.add_column("Select", style="white", width=6)
            selection_table.add_column("Group Name", style="cyan")
            selection_table.add_column("Channels", style="green")
            selection_table.add_column("Selected", style="yellow", width=10)
            
            for i in range(start_idx, end_idx):
                group_name = group_names[i]
                count = len(groups[group_name])
                is_selected = group_name in self.state.selected_groups
                selector = f"[{i+1}]"
                selected_status = "✅" if is_selected else "❌"
                
                selection_table.add_row(
                    selector,
                    group_name,
                    f"{count:,}",
                    selected_status
                )
            
            self.console.print(Panel(selection_table, border_style="green"))
            
            # Selection summary
            selected_count = len(self.state.selected_groups)
            total_channels = sum(len(groups[group]) for group in self.state.selected_groups)
            
            summary_panel = Panel(
                f"Selected: [bold green]{selected_count}[/bold green] groups "
                f"([bold cyan]{total_channels:,}[/bold cyan] channels)\n\n"
                "[dim]Commands:[/dim]\n"
                "[yellow]numbers[/yellow] - Toggle groups • [yellow]a[/yellow] - Select all • [yellow]n[/yellow] - Select none\n"
                "[yellow]p[/yellow] - Previous page • [yellow]d[/yellow] - Next page • [yellow]e[/yellow] - Export • [yellow]c[/yellow] - Cancel",
                title="📦 Export Summary",
                border_style="blue"
            )
            self.console.print(summary_panel)
            
            # Handle input
            command = Prompt.ask(
                "\n[cyan]Command[/cyan]",
                choices=[str(i+1) for i in range(start_idx, end_idx)] + 
                       ['a', 'n', 'p', 'd', 'e', 'c'],
                default="c"
            ).lower()
            
            if command.isdigit():
                idx = int(command) - 1
                if start_idx <= idx < end_idx:
                    group_name = group_names[idx]
                    if group_name in self.state.selected_groups:
                        self.state.selected_groups.remove(group_name)
                    else:
                        self.state.selected_groups.add(group_name)
            elif command == 'a':
                self.state.selected_groups.update(group_names)
            elif command == 'n':
                self.state.selected_groups.clear()
            elif command == 'p' and current_page > 0:
                current_page -= 1
            elif command == 'd' and end_idx < len(group_names):
                current_page += 1
            elif command == 'e':
                self._perform_export(groups)
                break
            elif command == 'c':
                break

    def _perform_export(self, groups: Dict[str, List[int]]):
        """Perform the actual export operation."""
        if not self.state.selected_groups:
            self._show_message("No groups selected!", "warning")
            return
            
        self.console.clear()
        
        # Export options
        format_choice = Prompt.ask(
            "Export format",
            choices=["m3u", "json", "m3u8"],
            default="m3u"
        )
        
        exclude = Confirm.ask("Exclude selected groups?", default=False)
        
        # Create filtered playlist
        filtered_pl = M3UPlaylist()
        filtered_pl.add_attributes(self.current_playlist.get_attributes())
        
        channels_exported = 0
        for channel in self.current_playlist:
            channel_group = channel.attributes.get('group-title', '')
            should_include = (channel_group in self.state.selected_groups) if not exclude else (channel_group not in self.state.selected_groups)
            
            if should_include:
                filtered_pl.append_channel(channel)
                channels_exported += 1
        
        # Generate filename and export
        groups_str = "_".join([g[:15] for g in list(self.state.selected_groups)[:2]])
        timestamp = int(time.time())
        filename = f"iptv_export_{groups_str}_{timestamp}.{format_choice}"
        
        try:
            if format_choice == "json":
                output = filtered_pl.to_json_playlist()
            elif format_choice == "m3u":
                output = filtered_pl.to_m3u_plus_playlist()
            elif format_choice == "m3u8":
                output = filtered_pl.to_m3u8_playlist()
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(output)
            
            self._show_message(f"✅ Exported {channels_exported} channels to {filename}", "success")
            
        except Exception as e:
            self._show_message(f"❌ Export failed: {e}", "error")

    def _show_message(self, message: str, msg_type: str = "info"):
        """Show a message dialog."""
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
        self.console.clear()
        help_text = """
[b]🎯 TUI IPTV Manager - Keyboard Controls[/b]

[bold cyan]Navigation:[/bold cyan]
• [yellow]↑↓[/yellow] arrows - Move selection
• [yellow]ENTER[/yellow] - Select option  
• [yellow]1-9[/yellow] - Quick jump to option
• [yellow]q[/yellow] - Quit application

[bold cyan]Export Mode:[/bold cyan]
• [yellow]numbers[/yellow] - Toggle group selection
• [yellow]a[/yellow] - Select all groups
• [yellow]n[/yellow] - Clear selection
• [yellow]p/d[/yellow] - Previous/next page
• [yellow]e[/yellow] - Export selected
• [yellow]c[/yellow] - Cancel export

[bold cyan]General:[/bold cyan]
• Follow on-screen prompts
• Use number keys for quick selection
• Most operations require a loaded playlist

[bold yellow]💡 Tip:[/bold yellow] Start by loading a playlist (option 1 or 2)!
        """
        self.console.print(Panel(help_text, title="❓ TUI Help Guide", border_style="green"))
        Prompt.ask("\n[dim]Press Enter to continue[/dim]")

    def _loading_screen(self):
        """Show loading screen."""
        self.console.clear()
        self.console.print("[yellow]Loading...[/yellow]")

    def _fallback_menu(self):
        """Fallback menu when rich is not available."""
        print("\n🎬 IPTV Manager - TUI Mode")
        print("========================")
        
        for i, (option, handler, op_type) in enumerate(self.menu_options):
            status = ""
            if op_type in ["overview", "groups", "tags", "export", "series", "search"] and not self.current_playlist:
                status = " [needs playlist]"
            elif op_type == "merge" and len(self.loaded_playlists) < 2:
                status = " [need 2+]"
                
            selector = ">" if i == self.state.selected_option else " "
            print(f"{selector} {i+1:2d}. {option}{status}")
        
        print(f"\nCurrent: {self.current_playlist.length() if self.current_playlist else 0} channels")
        print("Use numbers to select, 'q' to quit")
        
        choice = input("\nSelect: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(self.menu_options):
            self.state.selected_option = int(choice) - 1
            self._execute_menu_option()
        elif choice == "q":
            self._exit_tui()

    def _exit_tui(self):
        """Clean exit from TUI."""
        self.console.clear()
        self.console.print("[green]🎬 Thank you for using IPTV Manager! 👋[/green]")
        sys.exit(0)

    def _print_error(self, message: str):
        """Print error message."""
        if RICH_AVAILABLE:
            self.console.print(f"[red]❌ {message}[/red]")
        else:
            print(f"❌ {message}")


def check_dependencies():
    """Check TUI dependencies."""
    if not RICH_AVAILABLE:
        print("⚠️  Rich library not found. Install for full TUI experience:")
        print("   pip install rich")
        print("\nFalling back to basic interface...\n")


def main():
    """Main entry point."""
    check_dependencies()
    
    # Create and run TUI manager
    manager = TUI_IPTV_Manager()
    
    # Handle command line arguments
    if len(sys.argv) > 1:
        url = sys.argv[1]
        sanitize = len(sys.argv) <= 2 or sys.argv[2].lower() != '--no-sanitize'
        manager.load_playlist_from_url(url, sanitize)
    
    # Start TUI
    manager.run()


if __name__ == "__main__":
    main()
