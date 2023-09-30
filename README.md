# Takt

A command-line tool for tracking time, built with Rich and Typer.

## About the name

The name "Takt" is derived from the German word "Taktzeit" which is a measure
of time or cycle time. It is a key principle of lean manufacturing in the
industry. This term is used to describe the pace of production that aligns
production with customer demand.


## Installation

You can install `takt` using pip:

```bash
pipx install takt
```

## Usage

```bash
takt [options]
```

### Commands

- `check`: Logs the check-in or check-out time.
- `export`: Exports the logs to a CSV file.
- `import`: Imports logs from a CSV file.
- `summary`: Displays a summary of the tracked time.

## Examples

### Logging time

```bash
takt check
```

### Importing logs from a CSV file

```bash
takt import --file=file.csv
```

### Displaying a summary of the tracked time

```bash
takt summary
```

## Contribution

Any kind of contribution is welcome. Please refer to the
[Contribution Guidelines](CONTRIBUTING.md) for more details.
