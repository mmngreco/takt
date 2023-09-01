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
from datetime import date

import pandas as pd
import typer
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


def calculate_hours(records: list[dict], by_week: bool = False) -> dict[str, float]:
    summary_dict = defaultdict(float)
    last_in_time = None
    last_out_time = None

    for record in records:
        kind = record[KIND]
        timestamp = record[TIMESTAMP]
        week = record.get('week', None)
        year = record.get('year', None)

        group_by = f"{year}-W{week}" if by_week else timestamp.date().isoformat()

        if kind == 'in':
            last_in_time = timestamp
        else:
            last_out_time = timestamp

        if last_in_time and last_out_time:
            time_diff = last_out_time - last_in_time
            hours = time_diff.total_seconds() / 3600
            summary_dict[group_by] += hours
            last_in_time = None
            last_out_time = None

    return summary_dict



def display_summary_table(summary_dict: str | float):
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Day", style="dim")
    table.add_column("Hours", style="dim")

    for day, hours in summary_dict.items():
        h = str(int(hours)).zfill(2)
        m = str(int((hours - int(hours)) * 60)).zfill(2)
        table.add_row(day, f"{h}:{m}")

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
        data = pd.read_csv(self.filename, nrows=nrows)
        # clean trailing spaces
        data = strip_values(data)[self.columns]
        data.fillna('', inplace=True)
        data.timestamp = data.timestamp.astype("datetime64[ns]")
        return data

    def load(self, nrows=None):
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
    file_manager = FileManager(filename)
    last_kind = file_manager.first()[KIND]
    # build record
    timestamp = datetime.now().isoformat()
    kind = 'out' if last_kind == 'in' else 'in'
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
    file_manager = FileManager(filename)
    data = file_manager.read()
    table = Table(show_header=True, header_style="bold magenta")
    for column in data.columns:
        table.add_column(column, style="dim")
    for row in data.to_dict('records'):
        table.add_row(*row.values())
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
    file_manager = FileManager(filename)
    records = file_manager.load()
    summary_dict = calculate_hours(records)
    display_summary_table(summary_dict)


@app.command()
def wtd(filename: str = FILE_NAME):
    file_manager = FileManager(filename)
    today = date.today()
    year, week, _ = today.isocalendar()
    records = file_manager.records_of_week(year, week).to_dict('records')
    summary_dict = calculate_hours(records, by_week=True)
    display_summary_table(summary_dict)


if __name__ == "__main__":
    app()
