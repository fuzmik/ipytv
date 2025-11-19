#!/usr/bin/env python3
"""
Enhanced IPTV Playlist Manager - Advanced Colorful CLI Tool

A comprehensive tool for loading, analyzing, and managing IPTV playlists
with URL history, tag parsing, multiple playlist support, and group filtering.
"""

import sys
import os
import time
from typing import Dict, List, Optional
import json
import pickle
from typing import Dict, List, Optional, Set, Any
from pathlib import Path
from urllib.parse import urlparse

# Add color support
try:
    from colorama import init, Fore, Back, Style, just_fix_windows_console
    just_fix_windows_console()
    init(autoreset=True)
    COLORS_ENABLED = True
except ImportError:
    class DummyColors:
        def __getattr__(self, name):
            return ""
    Fore = Back = Style = DummyColors()
    COLORS_ENABLED = False

# Rich for advanced formatting
try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.text import Text
    from rich.prompt import Prompt, Confirm, IntPrompt
    from rich import box
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.columns import Columns
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# IPyTV imports
from ipytv import playlist
from ipytv.doctor import M3UDoctor, M3UPlaylistDoctor, IPTVChannelDoctor
from ipytv.utils import extract_series, is_episode_from_series, extract_show_name
from ipytv.channel import IPTVChannel, IPTVAttr
from ipytv.exceptions import URLException, MalformedPlaylistException
from ipytv.playlist import M3UPlaylist


class EnhancedIPTVManager:
    """Enhanced IPTV Playlist Manager with advanced features."""
    
    def __init__(self, data_dir: str = "iptv_data"):
        self.current_playlist = None
        self.loaded_playlists: Dict[str, M3UPlaylist] = {}  # name -> playlist
        self.console = Console() if RICH_AVAILABLE else None
        self.data_dir = Path(data_dir)
        self.history_file = self.data_dir / "url_history.json"
        self.playlists_file = self.data_dir / "saved_playlists.pkl"
        
        # Initialize data directory
        self.data_dir.mkdir(exist_ok=True)
        self.url_history = self._load_url_history()
        self.saved_playlists = self._load_saved_playlists()

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
    
    def _load_saved_playlists(self) -> Dict[str, Any]:
        """Load saved playlists from file."""
        try:
            if self.playlists_file.exists():
                with open(self.playlists_file, 'rb') as f:
                    return pickle.load(f)
        except Exception as e:
            self._print_error(f"Failed to load saved playlists: {e}")
        return {}
    
    def _save_saved_playlists(self):
        """Save playlists to file."""
        try:
            with open(self.playlists_file, 'wb') as f:
                pickle.dump(self.saved_playlists, f)
        except Exception as e:
            self._print_error(f"Failed to save playlists: {e}")
    
    def add_to_history(self, url: str, success: bool, channel_count: int = 0):
        """Add URL to history."""
        history_entry = {
            'url': url,
            'timestamp': time.time(),
            'success': success,
            'channel_count': channel_count,
            'domain': urlparse(url).netloc
        }
        
        # Remove existing entry if present
        self.url_history = [entry for entry in self.url_history if entry['url'] != url]
        
        # Add new entry at beginning
        self.url_history.insert(0, history_entry)
        
        # Keep only last 50 entries
        self.url_history = self.url_history[:50]
        
        self._save_url_history()
    
    def load_playlist_from_url(self, url: str, sanitize: bool = True, playlist_name: str = None) -> bool:
        """Load playlist from URL with progress indication."""
        try:
            if RICH_AVAILABLE:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    transient=True,
                ) as progress:
                    task = progress.add_task(f"Loading playlist from {url}", total=None)
                    pl = playlist.loadu(url)
                    progress.update(task, completed=1)
            else:
                print(f"{Fore.YELLOW}Loading playlist from: {url}{Style.RESET_ALL}")
                pl = playlist.loadu(url)
            
            # Sanitize if requested
            if sanitize and pl:
                if RICH_AVAILABLE:
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        transient=True,
                    ) as progress:
                        task = progress.add_task("Sanitizing playlist...", total=None)
                        pl = M3UPlaylistDoctor.sanitize(pl)
                        progress.update(task, completed=1)
                else:
                    print(f"{Fore.YELLOW}Sanitizing playlist...{Style.RESET_ALL}")
                    pl = M3UPlaylistDoctor.sanitize(pl)
            
            # Set as current playlist
            self.current_playlist = pl
            
            # Generate name if not provided
            if not playlist_name:
                domain = urlparse(url).netloc
                timestamp = time.strftime('%Y%m%d_%H%M%S')
                playlist_name = f"{domain}_{timestamp}"
            
            # Store in loaded playlists
            self.loaded_playlists[playlist_name] = pl
            
            # Add to history
            self.add_to_history(url, True, pl.length() if pl else 0)
            
            return True
            
        except URLException as e:
            self._print_error(f"Failed to load URL: {e}")
            self.add_to_history(url, False)
            return False
        except MalformedPlaylistException as e:
            self._print_error(f"Malformed playlist: {e}")
            self.add_to_history(url, False)
            return False
        except Exception as e:
            self._print_error(f"Unexpected error: {e}")
            self.add_to_history(url, False)
            return False
    
    def load_multiple_urls(self, urls: List[str], sanitize: bool = True):
        """Load multiple playlists from URLs."""
        success_count = 0
        
        if RICH_AVAILABLE:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                transient=False,
            ) as progress:
                task = progress.add_task("Loading multiple playlists...", total=len(urls))
                
                for url in urls:
                    progress.update(task, description=f"Loading {url[:50]}...")
                    if self.load_playlist_from_url(url, sanitize):
                        success_count += 1
                    progress.update(task, advance=1)
        else:
            for i, url in enumerate(urls):
                print(f"{Fore.CYAN}[{i+1}/{len(urls)}] Loading: {url}{Style.RESET_ALL}")
                if self.load_playlist_from_url(url, sanitize):
                    success_count += 1
        
        self._print_success(f"Successfully loaded {success_count}/{len(urls)} playlists")
    
    def load_from_history(self):
        """Load playlist from history."""
        if not self.url_history:
            self._print_warning("No URL history available!")
            return
        
        if RICH_AVAILABLE:
            history_table = Table(title="URL History", box=box.ROUNDED)
            history_table.add_column("#", style="white", width=4)
            history_table.add_column("URL", style="cyan")
            history_table.add_column("Channels", style="green", width=10)
            history_table.add_column("Status", style="yellow", width=8)
            history_table.add_column("Date", style="white", width=12)
            
            for i, entry in enumerate(self.url_history[:20]):
                status = "✓" if entry['success'] else "✗"
                status_color = "green" if entry['success'] else "red"
                date = time.strftime('%m/%d %H:%M', time.localtime(entry['timestamp']))
                url_preview = entry['url'][:60] + "..." if len(entry['url']) > 60 else entry['url']
                
                history_table.add_row(
                    str(i + 1),
                    url_preview,
                    str(entry.get('channel_count', 0)),
                    f"[{status_color}]{status}[/{status_color}]",
                    date
                )
            
            self.console.print(Panel(history_table, title="📜 URL History", title_align="left"))
            
            try:
                choice = IntPrompt.ask(
                    "Enter history number to load (0 to cancel)",
                    choices=[str(i) for i in range(0, min(21, len(self.url_history) + 1))],
                    default=0
                )
                
                if choice > 0 and choice <= len(self.url_history):
                    selected_url = self.url_history[choice - 1]['url']
                    sanitize = Confirm.ask("Sanitize playlist?")
                    self.load_playlist_from_url(selected_url, sanitize)
                    
            except Exception:
                self._print_info("Selection cancelled")
                
        else:
            print(f"{Fore.CYAN}{Style.BRIGHT}📜 URL History:{Style.RESET_ALL}")
            for i, entry in enumerate(self.url_history[:10]):
                status = "✓" if entry['success'] else "✗"
                date = time.strftime('%m/%d %H:%M', time.localtime(entry['timestamp']))
                print(f"{Fore.WHITE}{i+1:2d}. {Fore.CYAN}{entry['url']} {Fore.GREEN}[{entry.get('channel_count', 0)}] {Fore.YELLOW}[{status}] {Fore.WHITE}{date}{Style.RESET_ALL}")
            
            try:
                choice = input(f"{Fore.CYAN}Enter history number to load (0 to cancel): {Style.RESET_ALL}").strip()
                if choice.isdigit():
                    choice_num = int(choice)
                    if 0 < choice_num <= len(self.url_history):
                        selected_url = self.url_history[choice_num - 1]['url']
                        sanitize = input(f"{Fore.CYAN}Sanitize playlist? (y/n): {Style.RESET_ALL}").strip().lower() != 'n'
                        self.load_playlist_from_url(selected_url, sanitize)
            except Exception:
                self._print_info("Selection cancelled")

    def display_playlist_overview(self):
        """Display comprehensive playlist overview."""
        if not self.current_playlist:
            self._print_warning("No playlist loaded!")
            return
        
        pl = self.current_playlist
        total_channels = pl.length()
        
        if RICH_AVAILABLE:
            # Create overview panel
            overview_table = Table(title="Playlist Overview", box=box.ROUNDED)
            overview_table.add_column("Metric", style="cyan")
            overview_table.add_column("Value", style="white")
            
            overview_table.add_row("Total Channels", f"{total_channels:,}")
            
            # Group analysis
            groups = pl.group_by_attribute()
            overview_table.add_row("Unique Groups", f"{len(groups):,}")
            
            # URL analysis
            url_groups = pl.group_by_url()
            overview_table.add_row("Unique URLs", f"{len(url_groups):,}")
            
            # Series detection
            series_map, non_series = extract_series(pl)
            overview_table.add_row("Detected Series", f"{len(series_map):,}")
            
            # Attributes
            playlist_attrs = pl.get_attributes()
            overview_table.add_row("Playlist Attributes", f"{len(playlist_attrs):,}")
            
            self.console.print(Panel(overview_table, title="📊 Overview", title_align="left"))
            
        else:
            print(f"{Fore.CYAN}{Style.BRIGHT}📊 Playlist Overview:{Style.RESET_ALL}")
            print(f"{Fore.WHITE}Total Channels: {Fore.YELLOW}{total_channels:,}{Style.RESET_ALL}")
            
            groups = pl.group_by_attribute()
            print(f"{Fore.WHITE}Unique Groups: {Fore.YELLOW}{len(groups):,}{Style.RESET_ALL}")
            
            url_groups = pl.group_by_url()
            print(f"{Fore.WHITE}Unique URLs: {Fore.YELLOW}{len(url_groups):,}{Style.RESET_ALL}")
            
            series_map, non_series = extract_series(pl)
            print(f"{Fore.WHITE}Detected Series: {Fore.YELLOW}{len(series_map):,}{Style.RESET_ALL}")
            
            playlist_attrs = pl.get_attributes()
            print(f"{Fore.WHITE}Playlist Attributes: {Fore.YELLOW}{len(playlist_attrs):,}{Style.RESET_ALL}")
            print()

    def display_group_analysis(self, top_n: int = 10):
        """Display group analysis with top groups."""
        if not self.current_playlist:
            return
        
        groups = self.current_playlist.group_by_attribute()
        
        # Sort groups by channel count
        sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)
        
        if RICH_AVAILABLE:
            group_table = Table(title=f"Top {top_n} Groups", box=box.ROUNDED)
            group_table.add_column("Rank", style="white")
            group_table.add_column("Group Name", style="cyan")
            group_table.add_column("Channel Count", style="green", justify="right")
            group_table.add_column("Percentage", style="yellow", justify="right")
            
            total_channels = self.current_playlist.length()
            
            for i, (group_name, channel_indices) in enumerate(sorted_groups[:top_n]):
                count = len(channel_indices)
                percentage = (count / total_channels) * 100
                
                # Handle no-group case
                display_name = group_name if group_name != self.current_playlist.NO_GROUP_KEY else "[No Group]"
                
                group_table.add_row(
                    str(i + 1),
                    display_name,
                    f"{count:,}",
                    f"{percentage:.1f}%"
                )
            
            self.console.print(Panel(group_table, title="📁 Group Analysis", title_align="left"))
            
        else:
            print(f"{Fore.CYAN}{Style.BRIGHT}📁 Top {top_n} Groups:{Style.RESET_ALL}")
            total_channels = self.current_playlist.length()
            
            for i, (group_name, channel_indices) in enumerate(sorted_groups[:top_n]):
                count = len(channel_indices)
                percentage = (count / total_channels) * 100
                
                display_name = group_name if group_name != self.current_playlist.NO_GROUP_KEY else "[No Group]"
                
                print(f"{Fore.WHITE}{i+1:2d}. {Fore.CYAN}{display_name:<30} {Fore.GREEN}{count:>6,} {Fore.YELLOW}{percentage:>5.1f}%{Style.RESET_ALL}")
            print()

    def display_series_analysis(self):
        """Display series/episode analysis."""
        if not self.current_playlist:
            return
        
        series_map, non_series = extract_series(self.current_playlist, exclude_single=True)
        
        if RICH_AVAILABLE:
            if series_map:
                series_table = Table(title="Detected TV Series", box=box.ROUNDED)
                series_table.add_column("Series Name", style="cyan")
                series_table.add_column("Episodes", style="green", justify="right")
                series_table.add_column("Sample Episode", style="white")
                
                for series_name, series_playlist in list(series_map.items())[:15]:
                    episode_count = series_playlist.length()
                    sample_channel = series_playlist.get_channel(0) if episode_count > 0 else None
                    sample_name = sample_channel.name if sample_channel else "N/A"
                    
                    series_table.add_row(
                        series_name,
                        f"{episode_count:,}",
                        sample_name[:50] + "..." if len(sample_name) > 50 else sample_name
                    )
                
                self.console.print(Panel(series_table, title="🎭 Series Detection", title_align="left"))
            else:
                self.console.print(Panel("No series detected in this playlist", 
                                       title="🎭 Series Detection", title_align="left"))
                
        else:
            print(f"{Fore.CYAN}{Style.BRIGHT}🎭 Series Detection:{Style.RESET_ALL}")
            if series_map:
                for series_name, series_playlist in list(series_map.items())[:10]:
                    episode_count = series_playlist.length()
                    print(f"{Fore.CYAN}📺 {series_name}: {Fore.GREEN}{episode_count} episodes{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}No series detected in this playlist{Style.RESET_ALL}")
            print()

    def search_channels(self, pattern: str, search_fields: List[str] = None, case_sensitive: bool = False):
        """Search channels with pattern and display results."""
        if not self.current_playlist:
            self._print_warning("No playlist loaded!")
            return
        
        if search_fields is None:
            search_fields = ["name", "attributes.group-title"]
        
        results = self.current_playlist.search(pattern, search_fields, case_sensitive)
        
        if RICH_AVAILABLE:
            if results:
                search_table = Table(title=f"Search Results for '{pattern}'", box=box.ROUNDED)
                search_table.add_column("#", style="white")
                search_table.add_column("Channel Name", style="cyan")
                search_table.add_column("Group", style="green")
                search_table.add_column("URL", style="yellow")
                
                for i, channel in enumerate(results[:20]):
                    group = channel.attributes.get('group-title', 'N/A')
                    url_preview = channel.url[:50] + "..." if len(channel.url) > 50 else channel.url
                    
                    search_table.add_row(
                        str(i + 1),
                        channel.name,
                        group,
                        url_preview
                    )
                
                self.console.print(Panel(search_table, title="🔍 Search Results", title_align="left"))
                self.console.print(f"[dim]Found {len(results):,} matching channels[/dim]")
            else:
                self.console.print(Panel("No channels found matching your search criteria", 
                                       title="🔍 Search Results", title_align="left"))
                
        else:
            print(f"{Fore.CYAN}{Style.BRIGHT}🔍 Search Results for '{pattern}':{Style.RESET_ALL}")
            if results:
                for i, channel in enumerate(results[:15]):
                    group = channel.attributes.get('group-title', 'N/A')
                    print(f"{Fore.WHITE}{i+1:2d}. {Fore.CYAN}{channel.name} {Fore.GREEN}[{group}]{Style.RESET_ALL}")
                print(f"{Fore.DIM}Found {len(results):,} matching channels{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}No channels found matching your search criteria{Style.RESET_ALL}")
            print()

    def export_playlist(self, format_type: str = "json"):
        """Export playlist in different formats."""
        if not self.current_playlist:
            self._print_warning("No playlist loaded!")
            return
        
        try:
            if format_type.lower() == "json":
                output = self.current_playlist.to_json_playlist()
                filename = f"playlist_export_{int(time.time())}.json"
            elif format_type.lower() == "m3u":
                output = self.current_playlist.to_m3u_plus_playlist()
                filename = f"playlist_export_{int(time.time())}.m3u"
            elif format_type.lower() == "m3u8":
                output = self.current_playlist.to_m3u8_playlist()
                filename = f"playlist_export_{int(time.time())}.m3u8"
            else:
                self._print_error("Unsupported format. Use: json, m3u, or m3u8")
                return
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(output)
            
            self._print_success(f"Playlist exported successfully to: {filename}")
            
        except Exception as e:
            self._print_error(f"Export failed: {e}")

    def _load_playlist_interactive(self):
        """Interactive playlist loading."""
        url = input(f"{Fore.CYAN}Enter playlist URL: {Style.RESET_ALL}").strip()
        if not url:
            self._print_warning("URL cannot be empty!")
            return
        
        sanitize = input(f"{Fore.CYAN}Sanitize playlist? (y/n, default=y): {Style.RESET_ALL}").strip().lower()
        sanitize = sanitize != 'n'
        
        self.load_playlist_from_url(url, sanitize)
        
        if self.current_playlist:
            self._print_success(f"Successfully loaded playlist with {self.current_playlist.length():,} channels!")
    
    def parse_tvg_tags_analysis(self):
        """Analyze and display TVG tag usage across playlist."""
        if not self.current_playlist:
            self._print_warning("No playlist loaded!")
            return
        
        tag_stats = {}
        total_channels = self.current_playlist.length()
        
        for channel in self.current_playlist:
            for attr_name in channel.attributes:
                if attr_name.startswith('tvg-'):
                    tag_stats[attr_name] = tag_stats.get(attr_name, 0) + 1
        
        if RICH_AVAILABLE:
            if tag_stats:
                tag_table = Table(title="TVG Tag Analysis", box=box.ROUNDED)
                tag_table.add_column("TVG Tag", style="cyan")
                tag_table.add_column("Count", style="green", justify="right")
                tag_table.add_column("Percentage", style="yellow", justify="right")
                tag_table.add_column("Description", style="white")
                
                # Common tvg tag descriptions
                tag_descriptions = {
                    'tvg-id': 'Channel ID for EPG',
                    'tvg-name': 'Channel name for EPG',
                    'tvg-logo': 'Channel logo URL',
                    'tvg-language': 'Channel language',
                    'tvg-country': 'Channel country',
                    'tvg-url': 'EPG source URL',
                    'tvg-shift': 'EPG time shift',
                    'tvg-chno': 'Channel number',
                    'tvg-rec': 'Recording capability'
                }
                
                for tag, count in sorted(tag_stats.items(), key=lambda x: x[1], reverse=True):
                    percentage = (count / total_channels) * 100
                    description = tag_descriptions.get(tag, 'Unknown tag')
                    
                    tag_table.add_row(
                        tag,
                        f"{count:,}",
                        f"{percentage:.1f}%",
                        description
                    )
                
                self.console.print(Panel(tag_table, title="🏷️ TVG Tag Analysis", title_align="left"))
            else:
                self.console.print(Panel("No TVG tags found in playlist", 
                                       title="🏷️ TVG Tag Analysis", title_align="left"))
                
        else:
            print(f"{Fore.CYAN}{Style.BRIGHT}🏷️ TVG Tag Analysis:{Style.RESET_ALL}")
            if tag_stats:
                for tag, count in sorted(tag_stats.items(), key=lambda x: x[1], reverse=True):
                    percentage = (count / total_channels) * 100
                    print(f"{Fore.CYAN}{tag:<15} {Fore.GREEN}{count:>6,} {Fore.YELLOW}{percentage:>6.1f}%{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}No TVG tags found in playlist{Style.RESET_ALL}")
            print()
    
    def export_with_group_filter(self):
        """Enhanced export with interactive group filtering."""
        if not self.current_playlist:
            self._print_warning("No playlist loaded!")
            return
        
        # Get all groups
        groups = self.current_playlist.group_by_attribute()
        group_names = sorted([name for name in groups.keys() if name != self.current_playlist.NO_GROUP_KEY])
        
        if not group_names:
            self._print_warning("No groups found in playlist!")
            return
        
        if RICH_AVAILABLE:
            # Enhanced group selection with multi-column layout
            selected_groups = self._enhanced_group_selection(group_names, groups)
        else:
            selected_groups = self._simple_group_selection(group_names, groups)
        
        if not selected_groups:
            self._print_info("Export cancelled")
            return
        
        # Export options
        if RICH_AVAILABLE:
            export_panel = Panel(
                f"[cyan]Selected Groups:[/cyan] {len(selected_groups)}\n"
                f"[green]Total Channels:[/green] {self.current_playlist.length():,}\n"
                f"[yellow]Filtered Channels:[/yellow] {sum(len(groups[group]) for group in selected_groups):,}",
                title="📦 Export Summary",
                border_style="green"
            )
            self.console.print(export_panel)
            
            format_choice = Prompt.ask(
                "Export format",
                choices=["json", "m3u", "m3u8"],
                default="m3u"
            )
            
            exclude = Confirm.ask("Exclude selected groups instead of including?", default=False)
            
            filename_prompt = Prompt.ask(
                "Filename (leave empty for auto-generated)",
                default=""
            )
        else:
            print(f"{Fore.GREEN}📦 Export Summary:{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Selected Groups: {Fore.WHITE}{len(selected_groups)}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}Total Channels: {Fore.WHITE}{self.current_playlist.length():,}{Style.RESET_ALL}")
            filtered_count = sum(len(groups[group]) for group in selected_groups)
            print(f"{Fore.YELLOW}Filtered Channels: {Fore.WHITE}{filtered_count:,}{Style.RESET_ALL}")
            
            format_choice = input(f"{Fore.CYAN}Export format (json/m3u/m3u8, default=m3u): {Style.RESET_ALL}").strip().lower() or "m3u"
            exclude = input(f"{Fore.CYAN}Exclude selected groups? (y/n, default=n): {Style.RESET_ALL}").strip().lower() == 'y'
            filename_prompt = input(f"{Fore.CYAN}Filename (enter for auto): {Style.RESET_ALL}").strip()
        
        # Create filtered playlist
        filtered_pl = M3UPlaylist()
        filtered_pl.add_attributes(self.current_playlist.get_attributes())
        
        channels_exported = 0
        for channel in self.current_playlist:
            channel_group = channel.attributes.get('group-title', '')
            should_include = (channel_group in selected_groups) if not exclude else (channel_group not in selected_groups)
            
            if should_include:
                filtered_pl.append_channel(channel)
                channels_exported += 1
        
        # Generate filename
        if filename_prompt:
            filename = filename_prompt
            if not filename.endswith(f".{format_choice}"):
                filename += f".{format_choice}"
        else:
            group_desc = "excluded" if exclude else "selected"
            groups_str = "_".join([g[:15] for g in selected_groups[:2]])  # Limit filename length
            timestamp = int(time.time())
            filename = f"iptv_{groups_str}_{group_desc}_{timestamp}.{format_choice}"
        
        try:
            if format_choice == "json":
                output = filtered_pl.to_json_playlist()
            elif format_choice == "m3u":
                output = filtered_pl.to_m3u_plus_playlist()
            elif format_choice == "m3u8":
                output = filtered_pl.to_m3u8_playlist()
            else:
                self._print_error("Unsupported format")
                return
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(output)
            
            self._print_success(f"✅ Exported {channels_exported} channels to: {filename}")
            
        except Exception as e:
            self._print_error(f"Export failed: {e}")
    
    def _enhanced_group_selection(self, group_names: List[str], groups: Dict[str, List[int]]) -> List[str]:
        """Enhanced group selection with rich interface."""
        selected_groups = set()
        
        while True:
            # Create multi-column layout for groups
            group_tables = []
            items_per_column = 15
            total_columns = (len(group_names) + items_per_column - 1) // items_per_column
            
            for col_idx in range(total_columns):
                start_idx = col_idx * items_per_column
                end_idx = min(start_idx + items_per_column, len(group_names))
                
                column_table = Table(
                    title=f"Groups {start_idx+1}-{end_idx}",
                    box=box.SIMPLE,
                    show_header=True,
                    header_style="bold magenta"
                )
                column_table.add_column("#", style="white", width=4)
                column_table.add_column("Select", style="cyan", width=8)
                column_table.add_column("Group Name", style="green")
                column_table.add_column("Channels", style="yellow", justify="right", width=10)
                
                for i in range(start_idx, end_idx):
                    group_name = group_names[i]
                    count = len(groups[group_name])
                    is_selected = "✓" if group_name in selected_groups else " "
                    selection_status = "[green]✓[/green]" if group_name in selected_groups else "[dim] [/dim]"
                    
                    column_table.add_row(
                        str(i + 1),
                        selection_status,
                        group_name,
                        f"{count:,}"
                    )
                
                group_tables.append(column_table)
            
            # Display groups in columns
            self.console.print(Panel(Columns(group_tables), title="📋 Available Groups - Multi-Select", title_align="left"))
            
            # Selection options
            self.console.print("\n[bold cyan]Selection Options:[/bold cyan]")
            self.console.print("[white]• Enter group numbers (e.g., 1,3,5-10,15)[/white]")
            self.console.print("[white]• 'all' - Select all groups[/white]")
            self.console.print("[white]• 'none' - Clear selection[/white]")
            self.console.print("[white]• 'done' - Finish selection[/white]")
            self.console.print(f"[green]Currently selected: {len(selected_groups)} groups[/green]\n")
            
            choice = Prompt.ask(
                "Enter your selection",
                default="done"
            ).strip().lower()
            
            if choice == 'done':
                break
            elif choice == 'all':
                selected_groups = set(group_names)
                self._print_success(f"Selected all {len(group_names)} groups")
            elif choice == 'none':
                selected_groups.clear()
                self._print_info("Selection cleared")
            else:
                # Parse number ranges (e.g., "1,3,5-10,15")
                new_selections = set()
                try:
                    for part in choice.split(','):
                        part = part.strip()
                        if '-' in part:
                            start, end = part.split('-')
                            start_idx = int(start.strip()) - 1
                            end_idx = int(end.strip()) - 1
                            for idx in range(start_idx, end_idx + 1):
                                if 0 <= idx < len(group_names):
                                    new_selections.add(group_names[idx])
                        else:
                            idx = int(part.strip()) - 1
                            if 0 <= idx < len(group_names):
                                new_selections.add(group_names[idx])
                    
                    # Toggle selection for specified groups
                    for group in new_selections:
                        if group in selected_groups:
                            selected_groups.remove(group)
                        else:
                            selected_groups.add(group)
                    
                    self._print_success(f"Updated selection: {len(selected_groups)} groups selected")
                    
                except ValueError:
                    self._print_error("Invalid input. Please enter numbers or ranges.")
        
        return list(selected_groups)
    
    def _simple_group_selection(self, group_names: List[str], groups: Dict[str, List[int]]) -> List[str]:
        """Simple group selection for non-rich interface."""
        selected_groups = []
        
        while True:
            print(f"\n{Fore.CYAN}{Style.BRIGHT}📋 Available Groups:{Style.RESET_ALL}")
            for i, group_name in enumerate(group_names):
                count = len(groups[group_name])
                selected = "✓" if group_name in selected_groups else " "
                print(f"{Fore.WHITE}{i+1:3d}. [{selected}] {Fore.CYAN}{group_name:<35} {Fore.GREEN}{count:>5,}{Style.RESET_ALL}")
            
            print(f"\n{Fore.YELLOW}Selection Options:{Style.RESET_ALL}")
            print(f"{Fore.WHITE}• Enter group numbers (e.g., 1,3,5 or 1-5,10){Style.RESET_ALL}")
            print(f"{Fore.WHITE}• 'all' - Select all groups{Style.RESET_ALL}")
            print(f"{Fore.WHITE}• 'none' - Clear selection{Style.RESET_ALL}")
            print(f"{Fore.WHITE}• 'done' - Finish selection{Style.RESET_ALL}")
            print(f"{Fore.GREEN}Currently selected: {len(selected_groups)} groups{Style.RESET_ALL}")
            
            choice = input(f"\n{Fore.CYAN}Enter your selection: {Style.RESET_ALL}").strip().lower()
            
            if choice == 'done':
                break
            elif choice == 'all':
                selected_groups = group_names.copy()
                print(f"{Fore.GREEN}Selected all {len(group_names)} groups{Style.RESET_ALL}")
            elif choice == 'none':
                selected_groups.clear()
                print(f"{Fore.BLUE}Selection cleared{Style.RESET_ALL}")
            else:
                # Parse number ranges
                new_selections = set()
                try:
                    for part in choice.split(','):
                        part = part.strip()
                        if '-' in part:
                            start, end = part.split('-')
                            start_idx = int(start.strip()) - 1
                            end_idx = int(end.strip()) - 1
                            for idx in range(start_idx, end_idx + 1):
                                if 0 <= idx < len(group_names):
                                    new_selections.add(group_names[idx])
                        else:
                            idx = int(part.strip()) - 1
                            if 0 <= idx < len(group_names):
                                new_selections.add(group_names[idx])
                    
                    # Toggle selection
                    for group in new_selections:
                        if group in selected_groups:
                            selected_groups.remove(group)
                        else:
                            selected_groups.append(group)
                    
                    print(f"{Fore.GREEN}Updated selection: {len(selected_groups)} groups selected{Style.RESET_ALL}")
                    
                except ValueError:
                    print(f"{Fore.RED}Invalid input. Please enter numbers or ranges.{Style.RESET_ALL}")
        
        return selected_groups
    
    def manage_loaded_playlists(self):
        """Manage multiple loaded playlists."""
        if not self.loaded_playlists:
            self._print_warning("No playlists loaded!")
            return
        
        if RICH_AVAILABLE:
            pl_table = Table(title="Loaded Playlists", box=box.ROUNDED)
            pl_table.add_column("#", style="white", width=4)
            pl_table.add_column("Name", style="cyan")
            pl_table.add_column("Channels", style="green", width=10)
            pl_table.add_column("Groups", style="yellow", width=10)
            
            playlist_names = list(self.loaded_playlists.keys())
            
            for i, name in enumerate(playlist_names):
                pl = self.loaded_playlists[name]
                groups = len(pl.group_by_attribute())
                pl_table.add_row(str(i + 1), name, f"{pl.length():,}", f"{groups:,}")
            
            self.console.print(Panel(pl_table, title="📚 Loaded Playlists", title_align="left"))
            
            try:
                choice = IntPrompt.ask(
                    "Select playlist to make current (0 to cancel)",
                    choices=[str(i) for i in range(0, len(playlist_names) + 1)],
                    default=0
                )
                
                if choice > 0 and choice <= len(playlist_names):
                    selected_name = playlist_names[choice - 1]
                    self.current_playlist = self.loaded_playlists[selected_name]
                    self._print_success(f"Switched to playlist: {selected_name}")
                    
                # Additional management options
                action = Prompt.ask(
                    "Management action",
                    choices=["switch", "remove", "merge", "cancel"],
                    default="cancel"
                )
                
                if action == "remove":
                    remove_choice = IntPrompt.ask(
                        "Enter playlist number to remove",
                        choices=[str(i) for i in range(1, len(playlist_names) + 1)]
                    )
                    if remove_choice > 0:
                        removed_name = playlist_names[remove_choice - 1]
                        if removed_name in self.loaded_playlists:
                            del self.loaded_playlists[removed_name]
                            self._print_success(f"Removed playlist: {removed_name}")
                            
            except Exception:
                self._print_info("Management cancelled")
                
        else:
            print(f"{Fore.CYAN}{Style.BRIGHT}📚 Loaded Playlists:{Style.RESET_ALL}")
            playlist_names = list(self.loaded_playlists.keys())
            for i, name in enumerate(playlist_names):
                pl = self.loaded_playlists[name]
                print(f"{Fore.WHITE}{i+1:2d}. {Fore.CYAN}{name} {Fore.GREEN}[{pl.length():,} channels]{Style.RESET_ALL}")
            
            try:
                choice = input(f"{Fore.CYAN}Select playlist to make current (0 to cancel): {Style.RESET_ALL}").strip()
                if choice.isdigit():
                    choice_num = int(choice)
                    if 0 < choice_num <= len(playlist_names):
                        selected_name = playlist_names[choice_num - 1]
                        self.current_playlist = self.loaded_playlists[selected_name]
                        self._print_success(f"Switched to playlist: {selected_name}")
            except Exception:
                self._print_info("Selection cancelled")
    
    def merge_playlists(self, playlist_names: List[str] = None, merged_name: str = None):
        """Merge multiple playlists into one."""
        if not playlist_names:
            
            if not self.loaded_playlists:
                self._print_warning("No playlists loaded!")
                return
            
            playlist_names = self._select_multiple_playlists()
            if not playlist_names:
                return
        
        if not merged_name:
            merged_name = f"merged_{int(time.time())}"
        
        merged_pl = M3UPlaylist()
        total_channels = 0
        
        for name in playlist_names:
            if name in self.loaded_playlists:
                pl = self.loaded_playlists[name]
                merged_pl.append_channels(pl.get_channels())
                total_channels += pl.length()
        
        # Add to loaded playlists
        self.loaded_playlists[merged_name] = merged_pl
        self.current_playlist = merged_pl
        
        self._print_success(f"Merged {len(playlist_names)} playlists into '{merged_name}' with {total_channels} channels")
    
    def _select_multiple_playlists(self) -> List[str]:
        """Interactive multiple playlist selection."""
        if RICH_AVAILABLE:
            pl_table = Table(title="Select Playlists to Merge", box=box.ROUNDED)
            pl_table.add_column("#", style="white", width=4)
            pl_table.add_column("Name", style="cyan")
            pl_table.add_column("Channels", style="green", width=10)
            
            playlist_names = list(self.loaded_playlists.keys())
            
            for i, name in enumerate(playlist_names):
                pl = self.loaded_playlists[name]
                pl_table.add_row(str(i + 1), name, f"{pl.length():,}")
            
            self.console.print(Panel(pl_table, title="🔀 Merge Playlists", title_align="left"))
            
            try:
                choices = Prompt.ask(
                    "Enter playlist numbers to merge (comma-separated)",
                    default="1,2"
                )
                
                selected_names = []
                for choice in choices.split(','):
                    if choice.strip().isdigit():
                        idx = int(choice.strip()) - 1
                        if 0 <= idx < len(playlist_names):
                            selected_names.append(playlist_names[idx])
                
                return selected_names
                    
            except Exception:
                return []
        else:
            print(f"{Fore.CYAN}{Style.BRIGHT}🔀 Select Playlists to Merge:{Style.RESET_ALL}")
            playlist_names = list(self.loaded_playlists.keys())
            for i, name in enumerate(playlist_names):
                pl = self.loaded_playlists[name]
                print(f"{Fore.WHITE}{i+1:2d}. {Fore.CYAN}{name} {Fore.GREEN}[{pl.length():,} channels]{Style.RESET_ALL}")
            
            choices = input(f"{Fore.CYAN}Enter playlist numbers (comma-separated): {Style.RESET_ALL}").strip()
            
            selected_names = []
            for choice in choices.split(','):
                if choice.strip().isdigit():
                    idx = int(choice.strip()) - 1
                    if 0 <= idx < len(playlist_names):
                        selected_names.append(playlist_names[idx])
            
            return selected_names
    
    def display_enhanced_menu(self):
        """Display enhanced interactive menu."""
        while True:
            if RICH_AVAILABLE:
                self._display_enhanced_rich_menu()
            else:
                self._display_enhanced_simple_menu()
            
            choice = input(f"{Fore.CYAN}Enter your choice (1-12, q to quit): {Style.RESET_ALL}").strip().lower()
            
            if choice == 'q':
                self._print_info("Thank you for using Enhanced IPTV Manager! 👋")
                break
            elif choice == '1':
                self._load_playlist_interactive()
            elif choice == '2':
                self.load_from_history()
            elif choice == '3':
                self._load_multiple_interactive()
            elif choice == '4' and self.current_playlist:
                self.display_playlist_overview()
            elif choice == '5' and self.current_playlist:
                self.display_group_analysis()
            elif choice == '6' and self.current_playlist:
                self.parse_tvg_tags_analysis()
            elif choice == '7' and self.current_playlist:
                self.export_with_group_filter()
            elif choice == '8':
                self.manage_loaded_playlists()
            elif choice == '9' and len(self.loaded_playlists) >= 2:
                self.merge_playlists()
            elif choice == '10' and self.current_playlist:
                self.display_series_analysis()
            elif choice == '11' and self.current_playlist:
                self._search_interactive()
            elif choice == '12':
                self._show_enhanced_help()
            else:
                if not self.current_playlist and choice in ['4','5','6','7','10','11']:
                    self._print_warning("Please load a playlist first!")
                elif choice == '9' and len(self.loaded_playlists) < 2:
                    self._print_warning("Need at least 2 playlists to merge!")
                else:
                    self._print_error("Invalid choice!")
    
    def _load_multiple_interactive(self):
        """Interactive multiple URL loading."""
        if RICH_AVAILABLE:
            urls_input = Prompt.ask("Enter URLs (comma-separated or one per line, end with empty line)")
            urls = [url.strip() for url in urls_input.split(',') if url.strip()]
        else:
            print(f"{Fore.CYAN}Enter URLs (one per line, empty line to finish):{Style.RESET_ALL}")
            urls = []
            while True:
                url = input().strip()
                if not url:
                    break
                urls.append(url)
        
        if urls:
            sanitize = Confirm.ask("Sanitize playlists?") if RICH_AVAILABLE else \
                     input(f"{Fore.CYAN}Sanitize playlists? (y/n): {Style.RESET_ALL}").lower() != 'n'
            self.load_multiple_urls(urls, sanitize)
    
    def _search_interactive(self):
        """Interactive search."""
        pattern = input(f"{Fore.CYAN}Enter search pattern: {Style.RESET_ALL}").strip()
        if not pattern:
            self._print_warning("Search pattern cannot be empty!")
            return
        
        case_sensitive = input(f"{Fore.CYAN}Case sensitive? (y/n, default=n): {Style.RESET_ALL}").strip().lower() == 'y'
        
        self.search_channels(pattern, case_sensitive=case_sensitive)
    
    def _display_enhanced_rich_menu(self):
        """Display enhanced rich interactive menu."""
        # Create a beautiful header
        header_text = Text("🎬 ENHANCED IPTV PLAYLIST MANAGER", style="bold bright_magenta")
        header = Panel(header_text, style="bright_cyan", box=box.DOUBLE)
        self.console.print(header)
        
        # Current status panel
        status_info = []
        if self.current_playlist:
            status_info.append(f"[bold green]✓ Current Playlist:[/bold green] {self.current_playlist.length():,} channels")
        else:
            status_info.append("[yellow]⚠ No playlist loaded[/yellow]")
        
        if self.loaded_playlists:
            status_info.append(f"[bold blue]📚 Loaded:[/bold blue] {len(self.loaded_playlists)} playlists")
        
        if self.url_history:
            success_count = sum(1 for entry in self.url_history if entry.get('success', False))
            status_info.append(f"[bold cyan]📜 History:[/bold cyan] {success_count}/{len(self.url_history)} successful")
        
        if status_info:
            status_panel = Panel("\n".join(status_info), title="📊 Current Status", border_style="green")
            self.console.print(status_panel)
        
        # Main menu
        menu_table = Table(show_header=False, box=box.ROUNDED, padding=(0, 2))
        menu_table.add_column("Option", style="bold cyan", width=6)
        menu_table.add_column("Description", style="white")
        menu_table.add_column("Status", style="dim", width=12)
        
        menu_items = [
            ("1", "📥 Load Single Playlist", "Always"),
            ("2", "📜 Load from History", f"{len(self.url_history)} saved"),
            ("3", "📚 Load Multiple URLs", "Batch mode"),
            ("4", "📊 Playlist Overview", "Current only"),
            ("5", "📁 Group Analysis", "Top 10 groups"),
            ("6", "🏷️ TVG Tag Analysis", "Tag stats"),
            ("7", "💾 Smart Export", "Group filter"),
            ("8", "🔀 Manage Playlists", f"{len(self.loaded_playlists)} loaded"),
            ("9", "🔄 Merge Playlists", f"{len(self.loaded_playlists)} available"),
            ("10", "🎭 Series Detection", "Auto-detect"),
            ("11", "🔍 Search Channels", "Regex support"),
            ("12", "❓ Help & Guide", "Documentation"),
            ("q", "🚪 Exit Manager", "Safe exit")
        ]
        
        for key, desc, status in menu_items:
            # Color code based on availability
            if key in ['4','5','6','7','10','11'] and not self.current_playlist:
                status_style = "red"
            elif key == '9' and len(self.loaded_playlists) < 2:
                status_style = "red"
            else:
                status_style = "dim"
            
            menu_table.add_row(
                f"[bold cyan]{key}[/bold cyan]",
                desc,
                f"[{status_style}]{status}[/{status_style}]"
            )
        
        menu_panel = Panel(menu_table, title="🎯 Main Menu", border_style="bright_blue")
        self.console.print(menu_panel)
        
        # Quick tips
        tips = [
            "💡 Pro tip: Use option 7 for advanced group-based exporting",
            "💡 Try loading from history (option 2) for quick access",
            "💡 Merge playlists (option 9) to combine multiple sources"
        ]
        
        tips_panel = Panel("\n".join(tips), title="💡 Quick Tips", border_style="yellow")
        self.console.print(tips_panel)
        self.console.print()
    
    def _display_enhanced_simple_menu(self):
        """Display enhanced simple text menu."""
        print(f"{Fore.MAGENTA}{Style.BRIGHT}🎬 ENHANCED IPTV PLAYLIST MANAGER{Style.RESET_ALL}")
        print()
        
        # Status display
        if self.current_playlist:
            print(f"{Fore.GREEN}✓ Current Playlist: {self.current_playlist.length():,} channels{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}⚠ No playlist loaded{Style.RESET_ALL}")
        
        if self.loaded_playlists:
            print(f"{Fore.BLUE}📚 Loaded: {len(self.loaded_playlists)} playlists{Style.RESET_ALL}")
        
        if self.url_history:
            success_count = sum(1 for entry in self.url_history if entry.get('success', False))
            print(f"{Fore.CYAN}📜 History: {success_count}/{len(self.url_history)} successful{Style.RESET_ALL}")
        
        print()
        print(f"{Fore.CYAN}{Style.BRIGHT}🎯 Main Menu:{Style.RESET_ALL}")
        print()
        
        menu_items = [
            ("1", "📥 Load Single Playlist"),
            ("2", "📜 Load from History"),
            ("3", "📚 Load Multiple URLs"),
            ("4", "📊 Playlist Overview"),
            ("5", "📁 Group Analysis"),
            ("6", "🏷️ TVG Tag Analysis"),
            ("7", "💾 Smart Export"),
            ("8", "🔀 Manage Playlists"),
            ("9", "🔄 Merge Playlists"),
            ("10", "🎭 Series Detection"),
            ("11", "🔍 Search Channels"),
            ("12", "❓ Help & Guide"),
            ("q", "🚪 Exit Manager")
        ]
        
        for key, desc in menu_items:
            status = ""
            if key in ['4','5','6','7','10','11'] and not self.current_playlist:
                status = f"{Fore.RED} [needs playlist]{Style.RESET_ALL}"
            elif key == '9' and len(self.loaded_playlists) < 2:
                status = f"{Fore.RED} [need 2+ playlists]{Style.RESET_ALL}"
            
            print(f"{Fore.CYAN}{key}.{Style.RESET_ALL} {desc}{status}")
        
        print()
        print(f"{Fore.YELLOW}💡 Pro tip: Use option 7 for advanced group-based exporting{Style.RESET_ALL}")
        print()
    
    def _show_enhanced_help(self):
        """Display enhanced help information."""
        if RICH_AVAILABLE:
            help_text = """
[b]🎯 Enhanced IPTV Playlist Manager - Complete Guide[/b]

[bold cyan]🚀 Core Features:[/bold cyan]
• [green]Smart Loading[/green]: Load from URLs, history, or multiple sources
• [green]Advanced Analysis[/green]: Group statistics, TVG tag analysis, series detection
• [green]Smart Exporting[/green]: Filter by groups with multi-select interface
• [green]Playlist Management[/green]: Merge, switch between, and manage multiple playlists

[bold cyan]💾 Export Features (Option 7):[/bold cyan]
• [yellow]Multi-Column Group Display[/yellow]: View all groups in organized columns
• [yellow]Flexible Selection[/yellow]: Use numbers, ranges (1-5), or toggle existing selections
• [yellow]Smart Filtering[/yellow]: Include or exclude selected groups
• [yellow]Export Summary[/yellow]: See exactly what will be exported before saving

[bold cyan]🎮 Quick Start:[/bold cyan]
1. Load a playlist (option 1 or 2)
2. Analyze it (options 4-6) 
3. Export filtered content (option 7)
4. Manage multiple sources (options 8-9)

[bold cyan]🔗 Sample URLs:[/bold cyan]
• https://iptv-org.github.io/iptv/categories/entertainment.m3u
• https://iptv-org.github.io/iptv/categories/sports.m3u
• https://iptv-org.github.io/iptv/categories/news.m3u

[bold yellow]💡 Pro Tip:[/bold yellow] Use range selection (e.g., "1-5,10,15-20") in group export for quick bulk operations!
            """
            self.console.print(Panel(help_text, title="❓ Complete Help Guide", title_align="left", border_style="green"))
        else:
            print(f"{Fore.CYAN}{Style.BRIGHT}🎯 Enhanced IPTV Manager - Complete Guide{Style.RESET_ALL}")
            print()
            print(f"{Fore.GREEN}🚀 Core Features:{Style.RESET_ALL}")
            print("• Smart Loading: Load from URLs, history, or multiple sources")
            print("• Advanced Analysis: Group stats, TVG tags, series detection")
            print("• Smart Exporting: Filter by groups with multi-select")
            print("• Playlist Management: Merge and manage multiple playlists")
            print()
            print(f"{Fore.YELLOW}💾 Export Features (Option 7):{Style.RESET_ALL}")
            print("• Multi-Column Group Display: Organized group viewing")
            print("• Flexible Selection: Use numbers, ranges (1-5), or toggle")
            print("• Smart Filtering: Include or exclude selected groups")
            print("• Export Summary: Preview before saving")
            print()
            print(f"{Fore.CYAN}🎮 Quick Start:{Style.RESET_ALL}")
            print("1. Load a playlist (option 1 or 2)")
            print("2. Analyze it (options 4-6)")
            print("3. Export filtered content (option 7)")
            print("4. Manage multiple sources (options 8-9)")
            print()
            print(f"{Fore.BLUE}🔗 Sample URLs:{Style.RESET_ALL}")
            print("https://iptv-org.github.io/iptv/categories/entertainment.m3u")
            print("https://iptv-org.github.io/iptv/categories/sports.m3u")
            print("https://iptv-org.github.io/iptv/categories/news.m3u")
            print()
            print(f"{Fore.YELLOW}💡 Pro Tip: Use range selection (e.g., '1-5,10,15-20') in group export!{Style.RESET_ALL}")
            print()
    
    def _print_success(self, message: str):
        """Print success message."""
        if RICH_AVAILABLE:
            self.console.print(f"[bold green]✅ {message}[/bold green]")
        else:
            print(f"{Fore.GREEN}✅ {message}{Style.RESET_ALL}")
    
    def _print_error(self, message: str):
        """Print error message."""
        if RICH_AVAILABLE:
            self.console.print(f"[bold red]❌ {message}[/bold red]")
        else:
            print(f"{Fore.RED}❌ {message}{Style.RESET_ALL}")
    
    def _print_warning(self, message: str):
        """Print warning message."""
        if RICH_AVAILABLE:
            self.console.print(f"[bold yellow]⚠️  {message}[/bold yellow]")
        else:
            print(f"{Fore.YELLOW}⚠️  {message}{Style.RESET_ALL}")
    
    def _print_info(self, message: str):
        """Print info message."""
        if RICH_AVAILABLE:
            self.console.print(f"[bold blue]ℹ️  {message}[/bold blue]")
        else:
            print(f"{Fore.BLUE}ℹ️  {message}{Style.RESET_ALL}")


def check_dependencies():
    """Check and report on optional dependencies."""
    missing_rich = not RICH_AVAILABLE
    missing_colorama = not COLORS_ENABLED
    
    if missing_rich or missing_colorama:
        print("Optional dependencies missing for enhanced experience:")
        if missing_rich:
            print("  - rich: pip install rich (for advanced UI)")
        if missing_colorama:
            print("  - colorama: pip install colorama (for colors on Windows)")
        print()


def main():
    """Main entry point."""
    # Check dependencies
    check_dependencies()
    
    # Create and run enhanced manager
    manager = EnhancedIPTVManager()
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--multiple':
            # Load multiple URLs from command line
            urls = sys.argv[2:]
            if urls:
                manager.load_multiple_urls(urls)
        else:
            # Load single URL
            url = sys.argv[1]
            sanitize = len(sys.argv) <= 2 or sys.argv[2].lower() != '--no-sanitize'
            manager.load_playlist_from_url(url, sanitize)
    
    # Enter interactive mode
    manager.display_enhanced_menu()


if __name__ == "__main__":
    main()
