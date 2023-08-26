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

FILE_NAME = 'records.csv'


def load_csv(filename):
    records = []
    try:
        with open(filename, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                records.append(row)
    except FileNotFoundError:
        pass
    return records


def save_csv(filename, records):
    with open(filename, 'w', newline='') as file:
        fieldnames = ['type', 'timestamp', 'notes']
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(record)


@app.command()
def check(filename: str = FILE_NAME):
    records = load_csv(filename)
    now = datetime.now().isoformat()
    type_ = 'out' if records and records[0]['type'] == 'in' else 'in'
    records.insert(0, {'type': type_, 'timestamp': now})
    save_csv(filename, records)
    console.print(f"Check {type_} at {now}", style="green")


@app.command()
def display(filename: str = 'records.csv'):
    records = load_csv(filename)

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Type", style="dim", width=12)
    table.add_column("Timestamp", style="dim", width=30)

    for record in records:
        table.add_row(record['type'], record['timestamp'])

    console.print(table)


@app.command()
def summary(filename: str = 'records.csv'):
    records = load_csv(filename)

    summary_dict = defaultdict(float)  # Dictionary to hold the summarized data

    last_in_time = None
    last_out_time = None

    for record in records:
        type = record['type']
        timestamp = datetime.fromisoformat(record['timestamp'])
        day = (
            timestamp.date().isoformat()
        )  # Extract just the day (in ISO format)

        if type == 'in':
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
    with open(filename, 'w', newline='') as _:
        pass
    console.print("All records have been cleared.", style="red")


@app.command()
def edit(filename: str = FILE_NAME):
    editor = os.environ.get(
        'EDITOR', 'vim'
    )  # Usar vim como editor predeterminado si EDITOR no está definido
    try:
        subprocess.run([editor, filename])
    except FileNotFoundError:
        typer.echo(f"Editor not found {editor}. Be sure that {editor} is installed and accesible.")

@app.command("import")
def import_csv(source: str, target: str = FILE_NAME):
    """
    Importa registros desde un archivo CSV a otro.
    """
    try:
        source_records = load_csv(source)
        target_records = load_csv(target)
        target_records = source_records + target_records
        save_csv(target, target_records)
        console.print(f"Data imported form {source} to {target}.", style="green")

    except Exception as e:
        console.print(f"Error: {e}", style="red")


if __name__ == "__main__":
    app()
