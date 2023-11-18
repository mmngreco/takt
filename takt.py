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

License
-------
MIT License

TODO
----
- [o] Add plug-in system
- [ ] Add a command to create a gantt chart using mermaid
- [ ] Add a command to commit changes to git
- [ ] Implement multiple files (projects)

"""
from datetime import date
import os
import subprocess
from collections import defaultdict

import pandas as pd
import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()

DEFAULT_FILE = '~/.takt_file.csv'
FILE_NAME = os.path.expanduser(os.getenv('TAKT_FILE', DEFAULT_FILE))

TIMESTAMP = "timestamp"
KIND = "kind"
NOTES = "notes"
COLUMNS = [
    TIMESTAMP,
    KIND,
    NOTES,
]
SECONDS_TO_HOURS = 1 / 3600


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
        data.fillna('', inplace=True)
        data.timestamp = data.timestamp.apply(pd.Timestamp).astype("datetime64[ns]")
        return data


    def exists(self, create=True):
        if Path(self.filename).exists():
            return True
        if create:
            pd.DataFrame(columns=self.columns).to_csv(self.filename, index=False)
            return True
        return False


    def load(self, nrows=None) -> list[dict[str, float]]:
        data = self.read(nrows=nrows)
        return data.to_dict('records')

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
        return data.to_dict('records')[0]

    def import_from(self, source_filename):
        source_data = pd.read_csv(source_filename)
        target_data = pd.read_csv(self.filename)
        data = pd.concat([source_data, target_data])
        data.to_csv(self.filename, index=False)

    def records_of_week(self, year, week):
        df = self.read()
        df[TIMESTAMP] = pd.to_datetime(df[TIMESTAMP])
        df['week'] = df[TIMESTAMP].dt.strftime('%U')
        df['year'] = df[TIMESTAMP].dt.year
        return df[(df['week'] == str(week)) & (df['year'] == year)]



class DailyRef:
    @staticmethod
    def group(timestamp):
        group_by = timestamp.date().isoformat()
        return group_by

class WeekRef:
    @staticmethod
    def group(timestamp):
        year = timestamp.year
        week = timestamp.strftime('%U')
        group_by = f"{year}-W{week}"
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
        group_by = f"{year}-M{month}"
        return group_by


class AggRow:

    def __init__(self, group: str, total: float | int, collection: set[date]):
        self.group = group
        self.total = total
        self.collection = collection

    def to_dict(self) -> dict[str, str | float | set[date]]:
        return {
            'time_ref': self.group,
            'total': self.total,
            'days': self.collection,
        }

class Aggregator:
    def __init__(self, period: str = 'daily'):
        self.period = period
        if period == 'wtd':
            self.time_agg = WeekRef.group
        elif period == 'ytd':
            self.time_agg = YearRef.group
        elif period == 'mtd':
            self.time_agg = MonthRef.group
        elif period == 'daily':
            self.time_agg = DailyRef.group
        else:
            raise ValueError(f"Period {period} not supported.")

    @staticmethod
    def infer_last_out(records):
        if records[0][KIND] == "in":
            new_record = {
                KIND: "out",
                TIMESTAMP: pd.Timestamp.now(),
            }
            records.insert(0, new_record)
            msg = "NOTE: Last out was inferred using `Timestamp.now()`."
            console.print(msg)
        return records

    def calculate(self, records: list[FileRow]) -> list[AggRow]:
        last_in_time = None
        last_out_time = None

        records = self.infer_last_out(records)
        row_collection = []

        # loop over records
        for record in records:
            # get variables
            kind = record[KIND]
            timestamp = record[TIMESTAMP]
            note = record[NOTES]

            # update variables
            if kind == 'in':
                last_in_time = timestamp
            else:
                last_out_time = timestamp

            # only consider pairs of in/out
            if last_in_time and last_out_time:

                # calculate hours
                time_diff = last_out_time - last_in_time
                total_seconds = time_diff.total_seconds()
                total_hours = total_seconds * SECONDS_TO_HOURS
                group_by = self.time_agg(timestamp)
                date = timestamp.date()
                # save data
                new_row = dict(group=group_by, hours=total_hours, dates=set([date]))
                # breakpoint()
                if not row_collection:
                    row_collection.append(new_row)
                else:
                    pre_row = row_collection[-1]
                    if new_row["group"] == pre_row["group"]:
                        pre_row["hours"] += new_row["hours"]
                        pre_row["dates"].update(new_row["dates"])
                    else:
                        row_collection.append(new_row)

                # reset variables
                last_in_time = None
                last_out_time = None

        return row_collection



def format_time(hours: float) -> str:
    h = str(int(hours)).zfill(2)
    m = str(int((hours - int(hours)) * 60)).zfill(2)
    return f"{h}:{m}"


def display_summary_table(summary_dict: list[dict[str, str | float | int]], limit=10):
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Date", style="dim")
    table.add_column("Hours", style="dim")
    table.add_column("N.Days", style="dim")       # Nueva columna
    table.add_column("Avg Hours", style="dim")  # Nueva columna

    for i, row in enumerate(summary_dict):
        day = row['group']
        total_hours = row['hours']
        dates = row['dates']
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
    def __init__(self):
        self.row = FileRow
        self.filename = FILE_NAME
        self._file_manager = None
        self._aggregator = None

    @property
    def file_manager(self):
        file_manager = self._file_manager
        if file_manager is None:
            file_manager = FileManager(self.filename)
            self._file_manager = file_manager
        return file_manager

    def records(self, nrows=None):
        file_manager = self.file_manager
        return file_manager.load(nrows=nrows)

    def insert(self, timestamp, kind, notes):
        file_manager = self.file_manager
        file_manager.insert(**self.row(timestamp, kind, notes))

    def first(self):
        file_manager = self.file_manager
        return file_manager.first()

    def aggregate(self, period=None):
        aggregator = Aggregator(period)
        records = self.records()
        return aggregator.calculate(records)

    @staticmethod
    def command(*args, **kwargs):
        return app.command(*args, **kwargs)

    @staticmethod
    def print(msg, style=None):
        console.print(msg, style=style)


@Takt.command()
def check(notes: str = ""):
    """
    Check in or out.
    """
    t  = Takt()
    timestamp = pd.Timestamp.now()
    last_kind = t.first()
    # infer kind
    if last_kind is None or last_kind[KIND] == 'out':
        kind = 'in'
    else:
        kind = 'out'
    t.insert(timestamp, kind, notes)
    t.print(f"Check {kind} at {timestamp}", style="green")


@app.command()
def display():
    """
    Show all records.
    """
    t = Takt()
    data = t.records()

    table = Table(show_header=True, header_style="bold magenta")
    for column in data[0].keys():
        table.add_column(column, style="dim")
    for row in data:
        timestamp, kind, notes = row.values()
        timestamp = str(timestamp)
        table.add_row(timestamp, kind, notes)

    t.print(table)


@app.command()
def edit(filename: str = FILE_NAME):
    """
    Edit the records file.
    """
    editor = os.environ.get(
        'EDITOR',
        'vim',  # Vim by default
    )
    try:
        subprocess.run([editor, filename])
    except FileNotFoundError:
        typer.echo(
            f"`{editor}` not found, check if it is installed and accessible."
        )


@app.command()
def summary():
    """
    Daily summary.
    """
    t = Takt()
    summary_dict = t.aggregate(period='daily')
    display_summary_table(summary_dict)


@app.command()
def wtd(filename: str = FILE_NAME):
    """
    Week to date summary.
    """
    t = Takt()
    list_dict = t.aggregate(period='wtd')
    display_summary_table(list_dict)


@app.command()
def ytd():
    """
    Year to date summary.
    """
    t = Takt()
    list_dict = t.aggregate(period='ytd')
    display_summary_table(list_dict)


@app.command()
def mtd():
    """
    Month to date summary.
    """
    t = Takt()
    summary_dict = t.aggregate(period='mtd')
    display_summary_table(summary_dict)


if __name__ == "__main__":
    import importlib
    import pkgutil

    discovered_plugins = {
        name: importlib.import_module(name)
        for _, name, _
        in pkgutil.iter_modules()
        if name.startswith('takt_')
    }

    for name, plugin in discovered_plugins.items():
        app.add_typer(plugin.app)

    app()
