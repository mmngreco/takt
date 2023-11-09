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

"""
import os
import subprocess
from collections import defaultdict
from datetime import datetime

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



class Aggregator:
    def __init__(self, records: list[dict]):
        self.records = records

    def calculate(self, period: str | None = None) -> dict[str, float]:
        summary_dict = defaultdict(lambda: [0.0, set()])
        last_in_time = None
        last_out_time = None
        if self.records[0][KIND] == "in":
            new_record = {
                KIND: "out",
                TIMESTAMP: pd.Timestamp.now(),
            }
            self.records.insert(0, new_record)
            msg = "NOTE: Last out was inferred using `Timestamp.now()`."
            console.print(msg)

        for record in self.records:
            kind = record[KIND]
            timestamp = record[TIMESTAMP]
            week = timestamp.strftime('%U')
            year = timestamp.year
            month = timestamp.month

            if period == 'wtd':
                group_by = f"{year}-W{week}"
            elif period == 'ytd':
                group_by = f"{year}"
            elif period == 'mtd':
                group_by = f"{year}-M{month}"
            else:
                group_by = timestamp.date().isoformat()

            if kind == 'in':
                last_in_time = timestamp
            else:
                last_out_time = timestamp

            if last_in_time and last_out_time:
                time_diff = last_out_time - last_in_time
                hours = time_diff.total_seconds() / 3600
                summary_dict[group_by][0] += hours
                summary_dict[group_by][1].add(last_out_time.date())
                last_in_time = None
                last_out_time = None

        return summary_dict


def format_time(hours: float) -> str:
    h = str(int(hours)).zfill(2)
    m = str(int((hours - int(hours)) * 60)).zfill(2)
    return f"{h}:{m}"


def display_summary_table(summary_dict: dict[str, tuple[float, int]], limit=10):
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Date", style="dim")
    table.add_column("Hours", style="dim")
    table.add_column("Days", style="dim")  # Nueva columna
    table.add_column("Avg Hours", style="dim")  # Nueva columna

    for i, (day, (total_hours, days)) in enumerate(summary_dict.items()):
        num_days = len(days)
        total_hours_str = format_time(total_hours)
        avg_hours = total_hours / num_days if num_days else 0  # Media de horas
        avg_hours_str = format_time(avg_hours)

        table.add_row(day, total_hours_str, str(num_days), avg_hours_str)
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


    def load(self, nrows=None) -> dict[str, float]:
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


@app.command()
def check(notes: str = "", filename: str = FILE_NAME):
    """
    Check in or out.
    """
    file_manager = FileManager(filename)
    # NOTE: sorted by timestamp in descending order (most recent first)
    last_kind = file_manager.first()
    if last_kind is None or last_kind[KIND] == 'out':
        kind = 'in'
    else:
        kind = 'out'
    # build record
    timestamp = pd.Timestamp.now()
    # insert record
    file_manager.insert(
        **{
            TIMESTAMP: timestamp,
            KIND: kind,
            NOTES: notes,
        }
    )
    console.print(f"Check {kind} at {timestamp}", style="green")


@app.command()
def display(filename: str = FILE_NAME):
    """
    Show all records.
    """
    file_manager = FileManager(filename)
    data = file_manager.read()
    table = Table(show_header=True, header_style="bold magenta")
    for column in data.columns:
        table.add_column(column, style="dim")
    for row in data.to_dict('records'):
        timestamp, kind, notes = row.values()
        timestamp = str(timestamp)
        table.add_row(timestamp, kind, notes)
    console.print(table)


@app.command()
def clear(filename: str = FILE_NAME):
    """
    Remove all records from the records file.
    """
    with open(filename, 'w', newline='') as _:
        pass
    console.print("All records have been cleared.", style="red")


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


@app.command("import")
def import_csv(source: str, target: str = FILE_NAME):
    """
    Import records from source to target.
    """
    fm = FileManager(target)
    try:
        fm.import_from(source)
        console.print(
            f"Data imported form {source} to {target}.", style="green"
        )
    except Exception as e:
        console.print(f"Error: {e}", style="red")


@app.command()
def summary(filename: str = FILE_NAME):
    """
    Daily summary.
    """
    file_manager = FileManager(filename)
    records = file_manager.load()
    aggregator = Aggregator(records)
    summary_dict = aggregator.calculate()
    display_summary_table(summary_dict)


@app.command()
def wtd(filename: str = FILE_NAME):
    """
    Week to date summary.
    """
    file_manager = FileManager(filename)
    records = file_manager.load()
    aggregator = Aggregator(records)
    summary_dict = aggregator.calculate('wtd')
    display_summary_table(summary_dict)


@app.command()
def ytd(filename: str = FILE_NAME):
    """
    Year to date summary.
    """
    file_manager = FileManager(filename)
    records = file_manager.load()
    aggregator = Aggregator(records)
    summary_dict = aggregator.calculate('ytd')
    display_summary_table(summary_dict)


@app.command()
def mtd(filename: str = FILE_NAME):
    """
    Month to date summary.
    """
    file_manager = FileManager(filename)
    records = file_manager.load()
    aggregator = Aggregator(records)
    summary_dict = aggregator.calculate('mtd')
    display_summary_table(summary_dict)

# TODO: Add a command to create a gantt chart using mermaid
# TODO: Add a command to commit changes to git
# TODO: Implement multiple files (projects)


if __name__ == "__main__":
    app()
