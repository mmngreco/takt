package main

import (
	"os"
	"strings"
	"testing"
	"time"
)

func TestCalculateDuration(t *testing.T) {
	records := []Record{
		{time.Now().Add(-4 * time.Hour), "in", ""},
		{time.Now().Add(-2 * time.Hour), "out", ""},
	}

	tests := []struct {
		name    string
		period  string
		length  bool
		avgHrs  bool
		wantErr bool
	}{
		{"day", "day", true, true, false},
		{"week", "week", true, true, false},
		{"month", "month", true, true, false},
		{"year", "year", true, true, false},
		{"unsupported", "unsupported", false, false, true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := calculateDuration(records, tt.period)
			if (err != nil) != tt.wantErr {
				t.Errorf("calculateDuration() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if (len(got) != 0) != tt.length {
				t.Errorf("Unexpected length of results")
			}
			if tt.avgHrs {
				for _, aggRec := range got {
					if aggRec.AverageHours == 0 {
						t.Errorf("Expected non-zero average hours")
					}
				}
			}
		})
	}
}

func TestAggregateBy(t *testing.T) {
	now := time.Now()
	records := []Record{
		{now.Add(-23 * time.Hour), "out", "Note1"},
		{now.Add(-24 * time.Hour), "in", "Note1"},
	}

	labeler := func(t time.Time) string {
		return t.Format("2006-01-02")
	}

	got := aggregateBy(records, labeler)

	if len(got) != 1 {
		t.Errorf("Expected 1 aggregation record, got %d", len(got))
	}
	for k, v := range got {
		if v.TotalHours != 1 {
			t.Errorf("For key %s, expected 1 hours, got %.2f \n %+v", k, v.TotalHours, got)
		}
	}
}

func TestInferLastOut(t *testing.T) {
	records := []Record{
		{time.Now().Add(-2 * time.Hour), "in", ""},
	}

	n := inferLastOut(&records)

	if n != 1 {
		t.Errorf("Expected to infer 1 'out' record, inferred %d", n)
	}

	if records[0].Kind != "out" {
		t.Errorf("Expected first record to be 'out', got '%s'", records[0].Kind)
	}
}

func TestReadRecords(t *testing.T) {
	dummyCSV := `timestamp,kind,notes
2020-02-01T00:00:00Z,in,Note2
2020-01-01T01:00:00Z,out,Note1
2020-01-01T00:00:00Z,in,Note1
`
	// Create test file
	err := os.WriteFile(FileName, []byte(dummyCSV), 0644)
	if err != nil {
		t.Fatalf("Failed to create file for testing: %v", err)
	}
	defer os.Remove(FileName) // clean up

	records, err := readRecords(-1)
	if err != nil {
		t.Fatalf("Failed to read records: %v", err)
	}

	if len(records) != 3 {
		t.Errorf("Expected 3 records, got %d", len(records))
	}
}

// TODO: improve this
func TestCheckAction(t *testing.T) {
	// Create a temporary file to simulate the CSV records file
	// You may need to specify a unique temp file for concurrent tests.
	tempFile, err := os.CreateTemp("", "test_checkAction.csv")
	if err != nil {
		t.Fatalf("Failed to create temp file: %v", err)
	}
	defer os.Remove(tempFile.Name()) // clean up

	// Write initial record to the temp file
	csvContent := "timestamp,kind,notes\n"
	if _, err := tempFile.WriteString(csvContent); err != nil {
		t.Fatalf("Failed to write to temp file: %v", err)
	}
	tempFile.Close()

	checkAction(tempFile.Name(), "Test Note")

	// Read the modified file content
	modifiedFile, err := os.Open(tempFile.Name())
	if err != nil {
		t.Fatalf("Failed to open modified temp file: %v", err)
	}
	defer modifiedFile.Close()

	var _gotCsvContent []byte
	if _gotCsvContent, err = os.ReadFile(modifiedFile.Name()); err != nil {
		t.Fatalf("Failed to read modified temp file: %v", err)
	}
	gotCsvContentList := strings.Split(string(_gotCsvContent), "\n")

	if len(gotCsvContentList) == len(csvContent) {
		t.Errorf("Expected modified file content, but no changes detected \nGot:\n%+v\n\nExpected:\n%+v", gotCsvContentList, csvContent)
	}
}

// func TestWriteRecords(t *testing.T) {
// 	tempFileName := "/tmp/testfile.csv"
// 	// create file
// 	_, err := os.Create(tempFileName)
// 	if err != nil {
// 		t.Fatalf("Failed to create test file: %v", err)
// 	}
// 	defer os.Remove(tempFileName) // cleanup after test
//
// 	err = writeRecords(tempFileName, strings.Join(header, ","))
// 	if err != nil {
// 		t.Fatalf("writeRecords() error: %v", err)
// 	}
// 	err = writeRecords(tempFileName, "2021-01-01T00:00:00Z,in,Test Note")
// 	if err != nil {
// 		t.Fatalf("writeRecords() error: %v", err)
// 	}
//
// 	contents, err := os.ReadFile(tempFileName)
// 	if err != nil {
// 		t.Fatalf("Failed to read test file: %v", err)
// 	}
//
// 	expected := "timestamp,kind,notes\n2021-01-01T00:00:00Z,in,Test Note\n"
// 	if string(contents) != expected {
// 		t.Errorf("File contents expected:\n%s\ngot:\n%s", expected, string(contents))
// 	}
// }
