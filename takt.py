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
import csv
import os
import subprocess
from collections import defaultdict
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table


app = typer.Typer()
console = Console()

DEFAULT_FILE = '~/.takt_file.csv'
FILE_NAME = os.path.expanduser(os.getenv('TAKT_FILE', DEFAULT_FILE))
COLUMNS = (
    'timestamp',
    'type',
    'notes',
)


class FileManager:
    columns = COLUMNS

    def __init__(self, filename):
        self.filename = filename

    def load(self, nlines=None):
        with open(self.filename, 'r') as f:
            reader = csv.reader(f)
            header = [h.strip() for h in next(reader)]
            data = []
            for i, row in enumerate(reader):
                if nlines is not None and i >= nlines:
                    break
                row = [item.strip() for item in row]
                record = dict(zip(header, row))
                data.append(record)
        return data

    def save(self, records):
        with open(self.filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.columns)
            writer.writeheader()
            for record in records:
                writer.writerow(record)

    def insert(self, *record):
        records = self.load()
        record = dict(zip(self.columns, record))
        records.insert(0, record)
        self.save(records)

    def table(self):
        table = Table(show_header=True, header_style="bold magenta")
        for col in COLUMNS:
            table.add_column(col, style="dim")
        records = self.load()
        for rec in records:
            table.add_row(*rec.values())
        return table

    def first_row(self):
        return self.load(nlines=1)

    def import_from(self, source_filename):
        source_manager = FileManager(source_filename)
        source_records = source_manager.load()
        target_records = self.load()
        target_records = source_records + target_records
        self.save(target_records)


@app.command()
def check(notes: str = "", filename: str = FILE_NAME):
    file_manager = FileManager(filename)
    TYPE = COLUMNS[0]
    last_type = file_manager.first_row()[0][TYPE]
    # build record
    timestamp = datetime.now().isoformat()
    type_ = 'out' if last_type == 'in' else 'in'
    # insert record
    file_manager.insert(type_, timestamp, notes)
    console.print(f"Check {type_} at {timestamp}", style="green")


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
    if records and records[0]['type'] == 'in':
        records.insert(
            0,
            {
                'type': 'out',
                'timestamp': datetime.now().isoformat(),
            },
        )
        console.print(
            "Note: The last 'in' record was inferred using 'now' as 'out'.",
            style="red",
        )

    for record in records:
        type_ = record['type']
        timestamp = datetime.fromisoformat(record['timestamp'])
        day = (
            timestamp.date().isoformat()
        )  # Extract just the day (in ISO format)

        if type_ == 'in':
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
