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
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()

DEFAULT_FILE = '~/.takt_file.csv'
FILE_NAME = os.path.expanduser(os.getenv('TAKT_FILE', DEFAULT_FILE))

COLUMNS = (
    'timestamp',  # as index in table method
    'kind',
    'notes',
)
KIND = 1
INDEX = 0

class FileManager:
    columns = COLUMNS

    def __init__(self, filename):
        self.filename = filename

    def load(self, nlines=None):
        data = pd.read_csv(self.filename)
        if nlines is not None:
            data = data.head(nlines)
        return data.to_dict('records')

    def save(self, records):
        data = pd.DataFrame(records)
        data.to_csv(self.filename, index=False)

    def insert(self, timestamp, kind, notes):
        records = self.load()
        record = dict(kind=kind, timestamp=timestamp, notes=notes)
        records.insert(0, record)
        self.save(records)

    def table(self):
        data = pd.read_csv(self.filename)
        return data

    def first_row(self):
        data = pd.read_csv(self.filename)
        return data.head(1).to_dict('records')

    def import_from(self, source_filename):
        source_data = pd.read_csv(source_filename)
        target_data = pd.read_csv(self.filename)
        data = pd.concat([source_data, target_data])
        data.to_csv(self.filename, index=False)


@app.command()
def check(notes: str = "", filename: str = FILE_NAME):
    file_manager = FileManager(filename)
    last_kind = file_manager.first_row()[0][COLUMNS[KIND]]
    # build record
    timestamp = datetime.now().isoformat()
    kind = 'out' if last_kind == 'in' else 'in'
    # insert record
    file_manager.insert(kind=kind, timestamp=timestamp, notes=notes)
    console.print(f"Check {kind} at {timestamp}", style="green")


@app.command()
def display(filename: str = FILE_NAME):
    file_manager = FileManager(filename)
    table = file_manager.table()
    console.print(table)


@app.command()
def summary(filename: str = FILE_NAME):
    file_manager = FileManager(filename)
    records = file_manager.load()

    summary_dict = defaultdict(float)  # Dictionary to hold the summarized data

    last_in_time = None
    last_out_time = None

    # Check if the first record is 'in' and add a current 'out' record
    if records and records[0]['kind'] == 'in':
        records.insert(
            0,
            {
                'kind': 'out',
                'timestamp': datetime.now().isoformat(),
            },
        )
        console.print(
            "Note: The last 'in' record was inferred using 'now' as 'out'.",
            style="red",
        )

    for record in records:
        kind = record['kind']
        timestamp = datetime.fromisoformat(record['timestamp'])
        day = (
            timestamp.date().isoformat()
        )  # Extract just the day (in ISO format)

        if kind == 'in':
            last_in_time = timestamp
        else:
            last_out_time = timestamp

        if last_in_time and last_out_time:
            # Calculate the time difference in hours
            time_diff = last_out_time - last_in_time
            hours = time_diff.total_seconds() / 3600

            summary_dict[day] += hours
            last_in_time = None
            last_out_time = None

    # Now let's display the summary using Rich's Table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Day", style="dim", width=20)
    table.add_column("Hours", style="dim", width=10)

    for day, hours in summary_dict.items():
        table.add_row(day, f"{hours:.2f}")

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
        'EDITOR', 'vim'
    )  # Usar vim como editor predeterminado si EDITOR no está definido
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


if __name__ == "__main__":
    app()
