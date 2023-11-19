# Takt

A command-line tool for tracking time, built with Rich and Typer. Takt is
extensible with plugins, you can create you own pluging to make takt even
better check out the [Plugins](#plugins) section.

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

Or directly from the repository:

```bash
git clone https://github.com/yourusername/takt.git
cd takt
pip install .
```

## Usage

```bash
takt --help
```

### Commands

- `help`: Displays help message.
- `check`: Logs the check-in or check-out time.
- `summary`: Exports the logs to a CSV file.

## Examples

### Logging time

```bash
takt check
```


### Displaying a summary of the tracked time

```bash
takt summary
```


## Plugins

You can create your own plugins to extend takt as you want. Check how to do it
[here](https://github.com/mmngreco/takt_plugin).

> [!NOTE]
>
> Don't forget to share your plugin with me. I would be glad to see how you use
> `takt`.



<!--
## Contribution

Any kind of contribution is welcome. Please refer to the
[Contribution Guidelines](CONTRIBUTING.md) for more details.
-->
