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

Usage
-----
From the command line:

     takt start "Task Name"
     takt stop
     takt list
     takt wtd
     takt mtd
     takt ytd

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

import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer()
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
DTYPE = {
    TIMESTAMP: "datetime64[ns]",
    KIND: "string",
    NOTES: "string",
}


class Aggregator:
    def __init__(self, records: list[dict]) -> None:
        self.records = records

    def group_by(self, record: dict) -> str:
        raise NotImplementedError

    def calculate(self) -> defaultdict[str, list]:
        summary_dict = defaultdict(lambda: [0.0, set()])
        last_in_time = None
        last_out_time = None
        records = self.records

        if records[0][KIND] == "in":
            new_record = {
                KIND: "out",
                TIMESTAMP: pd.Timestamp.now(),
            }
            records.insert(0, new_record)
            msg = "NOTE: Last out was inferred using `Timestamp.now()`."
            console.print(msg)

        for record in records:
            kind = record[KIND]
            timestamp = record[TIMESTAMP]
            # MONTH
            group_by = self.group_by(record)

            if kind == 'in':
                last_in_time = timestamp
            else:
                last_out_time = timestamp

            if last_in_time and last_out_time:
                duration = last_out_time - last_in_time
                hours = duration.total_seconds() / 3600
                summary_dict[group_by][0] += hours
                summary_dict[group_by][1].add(last_out_time.date())
                last_in_time = None
                last_out_time = None

        return summary_dict


class DailyAggregator(Aggregator):
    def group_by(self, record: dict) -> str:
          return record[TIMESTAMP].date().isoformat()


class WeeklyAggregator(Aggregator):
    def group_by(self, record: dict) -> str:
        return str(record[TIMESTAMP].isocalendar().week)


class MonthlyAggregator(Aggregator):
    def group_by(self, record: dict) -> str:
        return str(record[TIMESTAMP].month)

class YearlyAggregator(Aggregator):
    def group_by(self, record: dict) -> str:
        return str(record[TIMESTAMP].year)


def format_time(hours: float) -> str:
    h = str(int(hours)).zfill(2)
    m = str(int((hours - int(hours)) * 60)).zfill(2)
    return f"{h}:{m}"


def display_summary_table(summary_dict: dict[str, tuple[float, int]]):
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Date", style="dim")
    table.add_column("Hours", style="dim")
    table.add_column("Days", style="dim")
    table.add_column("Avg Hours", style="dim")

    for day, (total_hours, days, *_) in summary_dict.items():
        num_days = len(days)
        total_hours_str = format_time(total_hours)
        avg_hours = total_hours / num_days if num_days else 0
        avg_hours_str = format_time(avg_hours)

        table.add_row(day, total_hours_str, str(num_days), avg_hours_str)

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
    """
    File manager for records.

    The file is a CSV with the following columns:

                         timestamp , kind , notes
        2023-09-29 17:43:44.833919 , out  ,
        2023-09-29 14:00:56.778976 , in   ,
        2023-09-29 12:26:19.441427 , out  ,
        2023-09-29 09:26:19.441427 , in   ,

    """
    columns = COLUMNS
    dtype = DTYPE

    def __init__(self, filename):
        self.filename = filename

    def read(self, nrows=None):
        data = pd.read_csv(self.filename, nrows=nrows)
        # clean trailing spaces
        data = strip_values(data)[self.columns]
        data = data.astype(self.dtype)
        data["notes"] = data["notes"].fillna("")
        return data

    def load(self, nrows=None) -> dict[str, float]:
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
        return data.to_dict("records")[0]

    def import_from(self, source_filename):
        source_data = pd.read_csv(source_filename)
        target_data = pd.read_csv(self.filename)
        data = pd.concat([source_data, target_data])
        data.to_csv(self.filename, index=False)

    def records_of_week(self, year, week):
        df = self.read()
        df[TIMESTAMP] = pd.to_datetime(df[TIMESTAMP])
        df["week"] = df[TIMESTAMP].dt.strftime("%U")
        df["year"] = df[TIMESTAMP].dt.year
        return df[(df["week"] == str(week)) & (df["year"] == year)]


# ============================================================================
# CLI


@app.command()
def check(notes: str = "", filename: str = FILE_NAME):
    """
    Check in or out.
    """
    file_manager = FileManager(filename)
    last_kind = file_manager.first()[KIND]
    # build record
    timestamp = pd.Timestamp.now()
    kind = "out" if last_kind == "in" else "in"
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
def cat(filename: str = FILE_NAME):
    """
    Show all records.
    """
    file_manager = FileManager(filename)
    data = file_manager.read()
    data["timestamp"] = data["timestamp"].astype(str)
    table = Table(show_header=True, header_style="bold magenta")
    for column in data.columns:
        table.add_column(column, style="dim")
    for row in data.to_dict("records"):
        table.add_row(*row.values())
    console.print(table)


@app.command()
def clear(filename: str = FILE_NAME):
    """
    Remove all records from the records file.
    """
    with open(filename, "w", newline="") as _:
        pass
    console.print("All records have been cleared.", style="red")


@app.command()
def edit(filename: str = FILE_NAME):
    """
    Edit the records file.
    """
    editor = os.environ.get(
        "EDITOR",
        "vim",  # Vim by default
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
    agg = DailyAggregator(records)
    summary_dict = agg.calculate()
    display_summary_table(summary_dict)


@app.command()
def wtd(filename: str = FILE_NAME):
    """
    Week to date summary.
    """
    file_manager = FileManager(filename)
    records = file_manager.load()
    __import__('pdb').set_trace()
    agg = WeeklyAggregator(records)
    summary_dict = agg.calculate()
    display_summary_table(summary_dict)


@app.command()
def ytd(filename: str = FILE_NAME):
    """
    Year to date summary.
    """
    file_manager = FileManager(filename)
    records = file_manager.load()
    agg = YearlyAggregator(records)
    summary_dict = agg.calculate()
    display_summary_table(summary_dict)


@app.command()
def mtd(filename: str = FILE_NAME):
    """
    Month to date summary.
    """
    file_manager = FileManager(filename)
    records = file_manager.load()
    agg = MonthlyAggregator(records)
    summary_dict = agg.calculate()
    display_summary_table(summary_dict)


if __name__ == "__main__":
    app()
