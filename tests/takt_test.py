import datetime
from unittest.mock import patch

import pandas as pd
import pytest
from pandas import Timestamp

from takt import (
    DailyAggregator,
    FileManager,
    MonthlyAggregator,
    WeeklyAggregator,
    YearlyAggregator
)

TIMESTAMP, KIND, NOTES = FileManager.columns


@pytest.fixture
def aggregator_records():
    return [
        {KIND: "out", TIMESTAMP: Timestamp("2022-01-02 08:00")},
        {KIND: "in", TIMESTAMP: Timestamp("2022-01-02 07:00")},
        {KIND: "out", TIMESTAMP: Timestamp("2022-01-01 06:00")},
        {KIND: "in", TIMESTAMP: Timestamp("2022-01-01 05:00")},
    ]


def test_daily_aggregator(sample_records):
    aggregator = DailyAggregator(sample_records)
    obtained = aggregator.calculate()
    expected = {
        '2022-01-02': [1.0, {datetime.date(2022, 1, 2)}],
        '2022-01-01': [1.0, {datetime.date(2022, 1, 1)}],
    }
    assert obtained == expected


def test_weekly_aggregator(sample_records):
    aggregator = WeeklyAggregator(sample_records)
    obtained = aggregator.calculate()
    expected = {
        '52': [2.0, {datetime.date(2022, 1, 1), datetime.date(2022, 1, 2)}]
    }
    assert obtained == expected


def test_monthly_aggregator(sample_records):
    aggregator = MonthlyAggregator(sample_records)
    obtained = aggregator.calculate()
    expected = {
        '1': [2.0, {datetime.date(2022, 1, 1), datetime.date(2022, 1, 2)}]
    }
    assert obtained == expected


def test_yearly_aggregator(sample_records):
    aggregator = YearlyAggregator(sample_records)
    obtained = aggregator.calculate()
    expected = {
        '2022': [2.0, {datetime.date(2022, 1, 1), datetime.date(2022, 1, 2)}]
    }
    assert obtained == expected



@pytest.fixture
def filemanager_df():
    return pd.DataFrame({
        TIMESTAMP: ['2022-01-01 11:00', '2022-01-01 08:00'],
        KIND: ['out', 'in'],
        NOTES: ["break for a coffee", "starting work"],
    }).astype({
        TIMESTAMP: 'datetime64[ns]',
        KIND: "string[python]",
        NOTES: "string[python]",
    })


@patch('pandas.read_csv')
def test_filemanager_read(mock_read_csv, mock_df):
    mock_read_csv.return_value = mock_df
    fm = FileManager('dummy.csv')
    obtained = fm.read()
    expected = mock_df
    pd.testing.assert_frame_equal(obtained, expected)


@patch('pandas.read_csv')
@patch('pandas.DataFrame.to_csv')
def test_filemanager_save(mock_to_csv, mock_read_csv, mock_df):
    mock_read_csv.return_value = mock_df
    fm = FileManager('dummy.csv')
    fm.save(mock_df.to_dict('records'))
    mock_to_csv.assert_called()


@patch('pandas.read_csv')
def test_filemanager_load(mock_read_csv, mock_df):
    mock_read_csv.return_value = mock_df
    fm = FileManager('dummy.csv')
    obtained = fm.load()
    assert obtained == mock_df.to_dict('records')


@patch('pandas.read_csv')
def test_filemanager_first(mock_read_csv, mock_df):
    mock_read_csv.return_value = mock_df
    fm = FileManager('dummy.csv')
    obtained = fm.first()
    assert obtained == mock_df.iloc[0].to_dict()
