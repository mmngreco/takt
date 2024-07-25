"""
takt: A Command Line Time Tracking Tool
=======================================

This module provides a command line interface (CLI) tool for tracking time
spent on various tasks.

Features
--------
- Start a timer for a task
- Stop the current task and log the time
- List all tasks and their total time
- Delete a task

Usage
-----
From the command line:

    $ takt start "Task Name"
    $ takt stop
    $ takt list
    $ takt delete "Task Name"

Dependencies
------------
- rich: For pretty console output
- typer: For parsing command line arguments

Authors
-------
- Max Greco (mmngreco@gmail.com)

TODO
----
- Allow multiple out table formats (e.g., CSV, JSON, TABLE, MD, etc.)
- Add option to read partial records (e.g., last 10 records)

License
-------
MIT License
"""

import os
import subprocess
from typing import Callable
from typer.core import TyperGroup
import re

import pandas as pd
import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
from git import Repo


console = Console()

DEFAULT_FILE = "~/.takt_file.csv"
FILE_NAME = os.path.expanduser(os.getenv("TAKT_FILE", DEFAULT_FILE))

TIMESTAMP = "timestamp"
KIND = "kind"
NOTES = "notes"
COLUMNS = [
    TIMESTAMP,
    KIND,
    NOTES,
]
SECONDS_TO_HOURS = 1 / 3600


def load_plugins(prefix):
    import importlib
    import pkgutil

    out = {}
    modules = pkgutil.iter_modules()
    for _, name, _ in modules:
        if name.startswith(prefix):
            try:
                module = importlib.import_module(name)
            except Exception as e:
                console.print(f"\n[red]WARNING:[/] Plugin '{name}' not imported: {e}")
                module = None
            out[name] = module
    # modules_list = list(pkgutil.iter_modules())
    # breakpoint()
    return out


class FileRow(dict):
    def __init__(self, timestamp, kind, notes):
        super().__init__(timestamp=timestamp, kind=kind, notes=notes)


class FileManager:
    columns = COLUMNS

    def __init__(self, filename):
        self.filename = filename

    def read(self, nrows=None):
        if not self.exists():
            raise ValueError(f"File {self.filename} does not exist.")
        data = pd.read_csv(self.filename, nrows=nrows)
        if data.empty:
            return data
        # clean trailing spaces
        data = strip_values(data)[self.columns]
        data.fillna("", inplace=True)
        data.timestamp = data.timestamp.apply(pd.Timestamp).astype("datetime64[ns]")
        return data

    def exists(self, create=True):
        if Path(self.filename).exists():
            return True
        if create:
            pd.DataFrame(columns=self.columns).to_csv(self.filename, index=False)
            return True
        return False

    def load(self, nrows=None) -> list[dict[str, float | str]]:
        data = self.read(nrows=nrows)
        return data.to_dict("records")

    def save(self, records):
        data = pd.DataFrame(records)[self.columns]
        data.to_csv(self.filename, index=False)

    def insert(self, **kwargs):
        records = self.load()
        records.insert(0, kwargs)
        self.save(records)

    def first(self):
        data = self.read(nrows=1)
        if data.empty:
            return None
        return data.to_dict("records")[0]

    def records_of_week(self, year, week):
        df = self.read()
        df[TIMESTAMP] = pd.to_datetime(df[TIMESTAMP])
        df["week"] = df[TIMESTAMP].dt.strftime("%U")
        df["year"] = df[TIMESTAMP].dt.year
        return df[(df["week"] == str(week)) & (df["year"] == year)]

    def commit(self, message="Commit by takt."):
        p = Path(self.filename)

        while not (p / ".git").exists():
            p = p.parent
            if p == Path.home():
                console.print("No git repository found.")
                return

        r = Repo(p)
        r.git.add(self.filename)
        r.git.commit("-m", message)


class DailyRef:
    @staticmethod
    def group(timestamp):
        group_by = timestamp.date().isoformat()
        return group_by


class WeekRef:
    @staticmethod
    def group(timestamp):
        year = timestamp.year
        week = int(timestamp.strftime("%U"))
        group_by = f"{year}-W{week:02d}"
        return group_by


class YearRef:
    @staticmethod
    def group(timestamp):
        year = timestamp.year
        group_by = f"{year}"
        return group_by


class MonthRef:
    @staticmethod
    def group(timestamp):
        year = timestamp.year
        month = timestamp.month
        group_by = f"{year}-M{month:02d}"
        return group_by


class Aggregator:
    def __init__(self, period: str = "daily"):
        self.period = period
        self.deferred = []
        if period == "wtd":
            self.time_agg = WeekRef.group
        elif period == "ytd":
            self.time_agg = YearRef.group
        elif period == "mtd":
            self.time_agg = MonthRef.group
        elif period == "daily":
            self.time_agg = DailyRef.group
        else:
            raise ValueError(f"Period {period} not supported.")

    def infer_last_out(self, records):
        if records[0][KIND] == "in":
            new_record = {
                KIND: "out",
                TIMESTAMP: pd.Timestamp.now(),
                NOTES: "Inferred by takt.",
            }
            records.insert(0, new_record)

            def deferred():
                msg = "NOTE: Last out was inferred using `Timestamp.now()`."
                console.print(msg)

            self.deferred.append(deferred)
        return records

    def calculate(self, records: list[dict]) -> list[dict]:
        records = self.infer_last_out(records)
        row_collection = []
        last_in_time = None
        last_out_time = None

        for record in records:
            # get variables
            timestamp = record[TIMESTAMP]

            # update variables
            if record[KIND] == "in":
                last_in_time = timestamp
            else:
                last_out_time = timestamp

            if last_in_time and last_out_time:
                group_by = self.time_agg(timestamp)
                total_hours = (
                    last_out_time - last_in_time
                ).total_seconds() * SECONDS_TO_HOURS
                date = timestamp.date()
                note = record[NOTES]

                row = [group_by, total_hours, [date], [note]]
                row_collection.append(row)

                # reset variables
                last_in_time = None
                last_out_time = None

        # aggregate to pandas
        table = pd.DataFrame(
            row_collection, columns=["group", "hours", "dates", "notes"]
        )
        summ = table.groupby("group").sum()
        summ.sort_index(inplace=True, ascending=False)
        summ.loc[:, "dates"] = summ.dates.apply(set)
        summ.loc[:, "notes"] = summ.notes.apply(set)
        summ.loc[:, "avg.hours"] = summ.hours / summ.dates.apply(len)
        summ = summ.reset_index()
        row_collection = summ.to_dict(orient="records")
        return row_collection


def format_time_explicit(hours: float, hours_by_day=7.5) -> str:
    d = int(hours / hours_by_day)
    h = int((hours % hours_by_day) // 1)
    m = int((hours % hours_by_day % 1) * 60)
    if d > 0:
        return f"{d:>02.0f} days{h:> 2.0f}H {m:> 3.0f} m"
    return f"{h:> 10.0f} H{m:> 3.0f} m"


def format_time(hours: float) -> str:
    h = str(int(hours)).zfill(2)
    m = str(int((hours - int(hours)) * 60)).zfill(2)
    return f"{h}:{m}"


class TableSummary:
    # WIP
    def __init__(self):
        self.table = None

    def build_table(self, records):
        table = Table(show_header=True, header_style="bold magenta")
        columns = [c for c in records[0].keys()]
        for column in columns:
            table.add_column(column, style="dim")

        for row in records:
            table.add_row(*row.values())
        self.table = table
        return table

    def show(self):
        console.print(self.table)


def display_summary_table(summary_dict: list[dict], limit=10):
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Date", style="dim")
    table.add_column("Hours", style="dim")
    table.add_column("N.Days", style="dim")  # Nueva columna
    table.add_column("Avg Hours", style="dim")  # Nueva columna

    for i, row in enumerate(summary_dict):
        day = row["group"]
        total_hours = row["hours"]
        dates = row["dates"]
        nobs = len(dates)

        total_hours_str = format_time(total_hours)
        avg_hours = total_hours / nobs if nobs else 0  # Media de horas
        avg_hours_str = format_time(avg_hours)

        table.add_row(day, total_hours_str, str(nobs), avg_hours_str)
        if i >= limit:
            break

    console.print(table)


def strip_values(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip()
    for c in df.columns:
        try:
            df[c] = df[c].str.strip()
        except AttributeError:
            pass
    return df


class Takt:
    """
    Interface for managing and processing data records, primarily focused on
    file system interactions and data aggregation.

    This class encapsulates functionalities for file management, data
    retrieval, insertion, and aggregation. It is designed to provide a
    structured and extendable approach to handling file-based data records.

    Attributes
    ----------
    row : FileRow
        Class representing a row in the data file.
    filename : str
        Name of the file to manage.
    _file_manager : FileManager, optional
        Internal manager for file operations.
    _aggregator : Aggregator, optional
        Internal tool for data aggregation.

    Methods
    -------
    file_manager()
        Accessor for the FileManager instance, lazily initialized.
    all_rows(nrows=None)
        Retrieves a list of data records from the file, optionally limited to `nrows`.
    insert_row(timestamp, kind, notes)
        Inserts a new row into the file with the given data.
    first_row()
        Returns the first data record from the file.
    aggregate(period="daily")
        Aggregates data records based on the specified period.
    register(*args, plugin_name=None, **kwargs)
        Static method. Registers a new command with an optional plugin name.
    print_console(msg, style=None)
        Static method. Prints a message to the console with optional styling.

    Examples
    --------
    >>> takt = Takt()
    >>> takt.insert_row("2023-01-01", "example", "This is a note.")
    >>> takt.print_console(takt_instance.first_row())

    Notes
    -----
    The class is intended to be used in environments where structured
    file-based data management is required. It is particularly useful for
    scenarios involving data aggregation and processing.
    """

    def __init__(self):
        self.row = FileRow
        self.filename = FILE_NAME
        self._file_manager = None
        self._aggregator = None
        self._deferred: list[Callable] = []

    def deferred(self):
        deferred = self._deferred

        class Deferred:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                for f in deferred:
                    f()
                deferred[:] = []

        return Deferred()

    @property
    def file_manager(self):
        """Get File manager."""
        file_manager = self._file_manager
        if file_manager is None:
            file_manager = FileManager(self.filename)
            self._file_manager = file_manager
        return file_manager

    def all_rows(self, nrows=None) -> list[dict[str, float | str]]:
        """Return records from file."""
        file_manager = self.file_manager
        return file_manager.load(nrows=nrows)

    def insert_row(self, timestamp, kind, notes):
        """Inser row in file."""
        file_manager = self.file_manager
        file_manager.insert(**self.row(timestamp, kind, notes))

    def first_row(self):
        """Return first row from file."""
        file_manager = self.file_manager
        return file_manager.first()

    def aggregate(self, period: str = "daily") -> list[dict]:
        """Aggregate records."""
        agg = Aggregator(period)
        records = self.all_rows()
        out = agg.calculate(records)
        self._deferred.extend(agg.deferred)
        return out

    @staticmethod
    def register(*args, plugin_name=None, **kwargs):
        """Decorator to register a new Takt command.

        It uses the typer command decorator. So use the same signature. This
        means that you can use this decorator to register a new command in
        typer as well.
        """
        if plugin_name is None:
            raise ValueError("plugin_name must be provided.")
        # ensure rich help panel is not duplicated
        kwargs = {**kwargs, "rich_help_panel": plugin_name}
        return app.command(*args, **kwargs)

    @staticmethod
    def print_console(msg, style=None):
        """Print message to console."""
        console.print(msg, style=style)


class AliasGroup(TyperGroup):
    _CMD_SPLIT_P = re.compile(r", ?")

    def get_command(self, ctx, cmd_name):
        cmd_name = self._group_cmd_name(cmd_name)
        return super().get_command(ctx, cmd_name)

    def _group_cmd_name(self, default_name):
        for cmd in self.commands.values():
            if cmd.name and default_name in re.split(self._CMD_SPLIT_P, cmd.name):
                return cmd.name
        return default_name


app = typer.Typer(cls=AliasGroup)


@app.command("check, c")
def check(notes: str = ""):
    """
    Check in or out.
    """
    t = Takt()
    timestamp = pd.Timestamp.now()
    last_kind = t.first_row()
    # infer kind
    if last_kind is None or last_kind[KIND] == "out":
        kind = "in"
    else:
        kind = "out"
    t.insert_row(timestamp, kind, notes)
    t.print_console(
        f"Check [bold magenta]{kind.upper()}[/] at {timestamp}", style="green"
    )


@app.command("display, d")
def display():
    """
    Show all records.
    """
    t = Takt()
    data = t.all_rows()

    table = Table(show_header=True, header_style="bold magenta")
    for column in data[0].keys():
        table.add_column(column, style="dim")
    for row in data:
        timestamp, kind, notes = row.values()
        timestamp = str(timestamp)
        table.add_row(timestamp, kind, notes)

    t.print_console(table)


@app.command("edit, e")
def edit():
    """
    Edit the records file.
    """
    editor = os.environ.get(
        "EDITOR",
        "vim",  # Vim by default
    )
    try:
        subprocess.run([editor, FILE_NAME])
    except FileNotFoundError:
        typer.echo(f"`{editor}` not found, check if it is installed and accessible.")


@app.command("day, summary, s")
def summary():
    """
    Daily summary.
    """
    t = Takt()
    with t.deferred():
        summary_dict = t.aggregate(period="daily")
        display_summary_table(summary_dict)


@app.command("week, wtd, w")
def wtd():
    """
    Week to date summary.
    """
    t = Takt()
    with t.deferred():
        list_dict = t.aggregate(period="wtd")
        display_summary_table(list_dict)


@app.command("year, ytd, y")
def ytd():
    """
    Year to date summary.
    """
    t = Takt()
    with t.deferred():
        list_dict = t.aggregate(period="ytd")
        display_summary_table(list_dict)


@app.command("month, mtd, m")
def mtd():
    """
    Month to date summary.
    """
    t = Takt()
    with t.deferred():
        summary_dict = t.aggregate(period="mtd")
        display_summary_table(summary_dict)


@app.command("commit, sync, cm")
def commit(message="Commit by takt."):
    """
    if TAKT_FILE is in a git repository it will commit and push the changes.
    """
    t = Takt()
    t.file_manager.commit(message)

plugins = load_plugins("takt_")

if __name__ == "__main__":
    app()
