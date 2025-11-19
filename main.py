#!/usr/bin/env python3
"""
IPTV Playlist Analyzer - Advanced Colorful CLI Tool

A comprehensive tool for loading, analyzing, and manipulating IPTV playlists
with colorful output and interactive features.
"""

import sys
import os
import time
from typing import Dict, List, Optional
import json

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
    from rich.prompt import Prompt, Confirm
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# IPyTV imports
from ipytv import playlist
from ipytv.doctor import M3UDoctor, M3UPlaylistDoctor
from ipytv.utils import extract_series, is_episode_from_series, extract_show_name
from ipytv.channel import IPTVAttr
from ipytv.exceptions import URLException, MalformedPlaylistException


class ColorfulIPTVAnalyzer:
    """Advanced IPTV Playlist Analyzer with colorful output and rich features."""
    
    def __init__(self):
        self.current_playlist = None
        self.console = Console() if RICH_AVAILABLE else None
        self.history = []
        
    def print_header(self):
        """Print a colorful header."""
        if RICH_AVAILABLE:
            title = Text("🎬 IPTV Playlist Analyzer 🎬", style="bold cyan")
            subtitle = Text("Advanced M3U Plus Playlist Tool", style="green")
            
            header_table = Table(show_header=False, box=box.DOUBLE_EDGE)
            header_table.add_row(title)
            header_table.add_row(subtitle)
            
            self.console.print(Panel(header_table, style="bright_magenta"))
            self.console.print()
        else:
            print(f"{Fore.CYAN}{Style.BRIGHT}🎬 IPTV Playlist Analyzer 🎬{Style.RESET_ALL}")
            print(f"{Fore.GREEN}Advanced M3U Plus Playlist Tool{Style.RESET_ALL}")
            print()
    
    def load_playlist_from_url(self, url: str, sanitize: bool = True) -> bool:
        """Load playlist from URL with progress indication."""
        try:
            if RICH_AVAILABLE:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    transient=True,
                ) as progress:
                    task = progress.add_task(f"Loading playlist from {url}", total=None)
                    self.current_playlist = playlist.loadu(url)
                    progress.update(task, completed=1)
            else:
                print(f"{Fore.YELLOW}Loading playlist from: {url}{Style.RESET_ALL}")
                self.current_playlist = playlist.loadu(url)
            
            # Sanitize if requested
            if sanitize and self.current_playlist:
                if RICH_AVAILABLE:
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        transient=True,
                    ) as progress:
                        task = progress.add_task("Sanitizing playlist...", total=None)
                        self.current_playlist = M3UPlaylistDoctor.sanitize(self.current_playlist)
                        progress.update(task, completed=1)
                else:
                    print(f"{Fore.YELLOW}Sanitizing playlist...{Style.RESET_ALL}")
                    self.current_playlist = M3UPlaylistDoctor.sanitize(self.current_playlist)
            
            # Add to history
            self.history.append({
                'url': url,
                'timestamp': time.time(),
                'channel_count': self.current_playlist.length() if self.current_playlist else 0
            })
            
            return True
            
        except URLException as e:
            self._print_error(f"Failed to load URL: {e}")
            return False
        except MalformedPlaylistException as e:
            self._print_error(f"Malformed playlist: {e}")
            return False
        except Exception as e:
            self._print_error(f"Unexpected error: {e}")
            return False
    
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
            print(f"{Fore.CYAN}{Style.Bright}📁 Top {top_n} Groups:{Style.RESET_ALL}")
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
    
    def display_playlist_attributes(self):
        """Display playlist-level attributes."""
        if not self.current_playlist:
            return
        
        attributes = self.current_playlist.get_attributes()
        
        if RICH_AVAILABLE:
            if attributes:
                attr_table = Table(title="Playlist Attributes", box=box.ROUNDED)
                attr_table.add_column("Attribute", style="cyan")
                attr_table.add_column("Value", style="white")
                
                for key, value in attributes.items():
                    attr_table.add_row(key, str(value))
                
                self.console.print(Panel(attr_table, title="🏷️ Playlist Attributes", title_align="left"))
            else:
                self.console.print(Panel("No playlist attributes found", 
                                       title="🏷️ Playlist Attributes", title_align="left"))
                
        else:
            print(f"{Fore.CYAN}{Style.BRIGHT}🏷️ Playlist Attributes:{Style.RESET_ALL}")
            if attributes:
                for key, value in attributes.items():
                    print(f"{Fore.CYAN}{key}: {Fore.WHITE}{value}{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}No playlist attributes found{Style.RESET_ALL}")
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
    
    def display_history(self):
        """Display loading history."""
        if not self.history:
            self._print_info("No history available")
            return
        
        if RICH_AVAILABLE:
            history_table = Table(title="Loading History", box=box.ROUNDED)
            history_table.add_column("Timestamp", style="white")
            history_table.add_column("URL", style="cyan")
            history_table.add_column("Channels", style="green", justify="right")
            
            for entry in self.history[-10:]:  # Show last 10 entries
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry['timestamp']))
                url_preview = entry['url'][:50] + "..." if len(entry['url']) > 50 else entry['url']
                
                history_table.add_row(
                    timestamp,
                    url_preview,
                    f"{entry['channel_count']:,}"
                )
            
            self.console.print(Panel(history_table, title="📜 History", title_align="left"))
            
        else:
            print(f"{Fore.CYAN}{Style.BRIGHT}📜 Loading History:{Style.RESET_ALL}")
            for entry in self.history[-5:]:
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry['timestamp']))
                print(f"{Fore.WHITE}{timestamp} {Fore.CYAN}{entry['url']} {Fore.GREEN}[{entry['channel_count']} channels]{Style.RESET_ALL}")
            print()
    
    def interactive_menu(self):
        """Display interactive menu."""
        while True:
            if RICH_AVAILABLE:
                self._display_rich_menu()
            else:
                self._display_simple_menu()
            
            choice = input(f"{Fore.CYAN}Enter your choice (1-9, q to quit): {Style.RESET_ALL}").strip().lower()
            
            if choice == 'q':
                self._print_info("Thank you for using IPTV Playlist Analyzer! 👋")
                break
            elif choice == '1':
                self._load_playlist_interactive()
            elif choice == '2' and self.current_playlist:
                self.display_playlist_overview()
            elif choice == '3' and self.current_playlist:
                self.display_group_analysis()
            elif choice == '4' and self.current_playlist:
                self.display_series_analysis()
            elif choice == '5' and self.current_playlist:
                self._search_interactive()
            elif choice == '6' and self.current_playlist:
                self.display_playlist_attributes()
            elif choice == '7' and self.current_playlist:
                self._export_interactive()
            elif choice == '8':
                self.display_history()
            elif choice == '9':
                self._show_help()
            else:
                if not self.current_playlist and choice in ['2','3','4','5','6','7']:
                    self._print_warning("Please load a playlist first!")
                else:
                    self._print_error("Invalid choice!")
    
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
    
    def _search_interactive(self):
        """Interactive search."""
        pattern = input(f"{Fore.CYAN}Enter search pattern: {Style.RESET_ALL}").strip()
        if not pattern:
            self._print_warning("Search pattern cannot be empty!")
            return
        
        case_sensitive = input(f"{Fore.CYAN}Case sensitive? (y/n, default=n): {Style.RESET_ALL}").strip().lower() == 'y'
        
        self.search_channels(pattern, case_sensitive=case_sensitive)
    
    def _export_interactive(self):
        """Interactive export."""
        format_type = input(f"{Fore.CYAN}Export format (json/m3u/m3u8, default=json): {Style.RESET_ALL}").strip().lower()
        if not format_type:
            format_type = "json"
        
        self.export_playlist(format_type)
    
    def _display_rich_menu(self):
        """Display rich interactive menu."""
        menu_table = Table(show_header=False, box=box.ROUNDED)
        menu_table.add_column("Option", style="cyan")
        menu_table.add_column("Description", style="white")
        
        menu_items = [
            ("1", "📥 Load Playlist from URL"),
            ("2", "📊 Show Playlist Overview"),
            ("3", "📁 Group Analysis"),
            ("4", "🎭 Series Detection"),
            ("5", "🔍 Search Channels"),
            ("6", "🏷️ Playlist Attributes"),
            ("7", "💾 Export Playlist"),
            ("8", "📜 View History"),
            ("9", "❓ Help"),
            ("q", "🚪 Quit")
        ]
        
        for key, desc in menu_items:
            menu_table.add_row(f"[bold]{key}[/bold]", desc)
        
        current_pl_info = ""
        if self.current_playlist:
            current_pl_info = f" | Loaded: {self.current_playlist.length():,} channels"
        
        self.console.print(Panel(menu_table, 
                               title=f"🎬 Main Menu{current_pl_info}", 
                               title_align="left"))
        self.console.print()
    
    def _display_simple_menu(self):
        """Display simple text menu."""
        print(f"{Fore.CYAN}{Style.BRIGHT}🎬 Main Menu{Style.RESET_ALL}")
        if self.current_playlist:
            print(f"{Fore.DIM}Loaded: {self.current_playlist.length():,} channels{Style.RESET_ALL}")
        print()
        print(f"{Fore.CYAN}1.{Style.RESET_ALL} 📥 Load Playlist from URL")
        print(f"{Fore.CYAN}2.{Style.RESET_ALL} 📊 Show Playlist Overview")
        print(f"{Fore.CYAN}3.{Style.RESET_ALL} 📁 Group Analysis")
        print(f"{Fore.CYAN}4.{Style.RESET_ALL} 🎭 Series Detection")
        print(f"{Fore.CYAN}5.{Style.RESET_ALL} 🔍 Search Channels")
        print(f"{Fore.CYAN}6.{Style.RESET_ALL} 🏷️ Playlist Attributes")
        print(f"{Fore.CYAN}7.{Style.RESET_ALL} 💾 Export Playlist")
        print(f"{Fore.CYAN}8.{Style.RESET_ALL} 📜 View History")
        print(f"{Fore.CYAN}9.{Style.RESET_ALL} ❓ Help")
        print(f"{Fore.CYAN}q.{Style.RESET_ALL} 🚪 Quit")
        print()
    
    def _show_help(self):
        """Display help information."""
        if RICH_AVAILABLE:
            help_text = """
[b]IPTV Playlist Analyzer Help[/b]

This tool allows you to analyze IPTV playlists in M3U Plus format with the following features:

• [cyan]Load Playlists[/cyan]: Load from any HTTP/HTTPS URL
• [cyan]Comprehensive Analysis[/cyan]: Channel counts, group analysis, series detection
• [cyan]Advanced Search[/cyan]: Regex-based search across channel properties
• [cyan]Data Sanitization[/cyan]: Automatic fixing of common playlist errors
• [cyan]Multiple Export Formats[/cyan]: JSON, M3U Plus, and standard M3U8

[i]Sample IPTV playlist URLs:[/i]
• https://iptv-org.github.io/iptv/categories/entertainment.m3u
• https://iptv-org.github.io/iptv/categories/music.m3u
• https://iptv-org.github.io/iptv/categories/news.m3u
            """
            self.console.print(Panel(help_text, title="❓ Help", title_align="left"))
        else:
            print(f"{Fore.CYAN}{Style.BRIGHT}❓ Help:{Style.RESET_ALL}")
            print("This tool analyzes IPTV playlists with features like:")
            print("• Load playlists from URLs")
            print("• Comprehensive playlist analysis")
            print("• Advanced search capabilities")
            print("• Data sanitization and export")
            print()
            print(f"{Fore.YELLOW}Sample URLs:{Style.RESET_ALL}")
            print("https://iptv-org.github.io/iptv/categories/entertainment.m3u")
            print("https://iptv-org.github.io/iptv/categories/music.m3u")
            print()
    
    def _print_success(self, message: str):
        """Print success message."""
        if RICH_AVAILABLE:
            self.console.print(f"[green]✓ {message}[/green]")
        else:
            print(f"{Fore.GREEN}✓ {message}{Style.RESET_ALL}")
    
    def _print_error(self, message: str):
        """Print error message."""
        if RICH_AVAILABLE:
            self.console.print(f"[red]✗ {message}[/red]")
        else:
            print(f"{Fore.RED}✗ {message}{Style.RESET_ALL}")
    
    def _print_warning(self, message: str):
        """Print warning message."""
        if RICH_AVAILABLE:
            self.console.print(f"[yellow]⚠ {message}[/yellow]")
        else:
            print(f"{Fore.YELLOW}⚠ {message}{Style.RESET_ALL}")
    
    def _print_info(self, message: str):
        """Print info message."""
        if RICH_AVAILABLE:
            self.console.print(f"[blue]ℹ {message}[/blue]")
        else:
            print(f"{Fore.BLUE}ℹ {message}{Style.RESET_ALL}")


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
    
    # Create and run analyzer
    analyzer = ColorfulIPTVAnalyzer()
    analyzer.print_header()
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        url = sys.argv[1]
        sanitize = len(sys.argv) <= 2 or sys.argv[2].lower() != '--no-sanitize'
        
        if analyzer.load_playlist_from_url(url, sanitize):
            analyzer.display_playlist_overview()
            analyzer.display_group_analysis()
        else:
            sys.exit(1)
    
    # Enter interactive mode
    analyzer.interactive_menu()


if __name__ == "__main__":
    main()
