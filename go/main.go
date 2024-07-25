package main

import (
	"bufio"
	"encoding/csv"
	"errors"
	"fmt"
	"io"
	"log"
	"os"
	"os/exec"
	"strconv"
	"time"

	"github.com/spf13/cobra"
)

const fileName = "csvfile.csv"

const timeFormat = time.RFC3339

const printDateFormat = "2006-01-02"

var header = []string{"timestamp", "kind", "notes"}

var rootCmd = &cobra.Command{
	Use:   "takt",
	Short: "A Command Line Time Tracking Tool",
}

var checkCmd = &cobra.Command{
	Use:     "check",
	Aliases: []string{"c"},
	Short:   "Check in or out",
	Run: func(cmd *cobra.Command, args []string) {
		notes := ""
		if len(args) > 0 {
			notes = args[0]
		}
		checkAction(fileName, notes)
	},
}

var catCmd = &cobra.Command{
	Use:     "display",
	Aliases: []string{"d"},
	Short:   "Show all records",
	Run: func(cmd *cobra.Command, args []string) {
		head := -1 // read all records
		var err error
		if len(args) > 0 {
			head, err = strconv.Atoi(args[0])
			if err != nil {
				log.Fatal(err)
			}
		}
		records, err := readRecords(head)
		if err != nil {
			log.Fatal(err)
		}
		printRecords(records)
	},
}

var editCmd = &cobra.Command{
	Use:     "edit",
	Aliases: []string{"e"},
	Short:   "Edit the records file",
	Run: func(cmd *cobra.Command, args []string) {
		editor := os.Getenv("EDITOR")
		edit_cmd := exec.Command(editor, fileName)
		edit_cmd.Stdin = os.Stdin
		edit_cmd.Stdout = os.Stdout
		err := edit_cmd.Run()
		if err != nil {
			log.Fatal(err)
		}
	},
}

var dailyCmd = &cobra.Command{
	Use:     "summary",
	Aliases: []string{"s"},
	Short:   "Daily summary",
	Run: func(cmd *cobra.Command, args []string) {
		summary("daily")
	},
}

var weekCmd = &cobra.Command{
	Use:     "wtd",
	Aliases: []string{"w"},
	Short:   "Week to date summary",
	Run: func(cmd *cobra.Command, args []string) {
		summary("weekly")
	},
}

var monthCmd = &cobra.Command{
	Use:     "mtd",
	Aliases: []string{"m"},
	Short:   "Month to date summary",
	Run: func(cmd *cobra.Command, args []string) {
		summary("monthly")
	},
}

var yearCmd = &cobra.Command{
	Use:     "ytd",
	Aliases: []string{"y"},
	Short:   "Year to date summary",
	Run: func(cmd *cobra.Command, args []string) {
		summary("yearly")
	},
}

type Record struct {
	Timestamp time.Time
	Kind      string
	Notes     string
}

type AggregatedRecord struct {
	Group        string
	TotalHours   float64
	Dates        []string
	Notes        []string
	AverageHours float64
}

func summary(offset string) {
	println(offset)
	records, err := readRecords(-1)
	if err != nil {
		log.Fatal(err)
	}
	agg, err := calculateDuration(records, offset)
	if err != nil {
		log.Fatalf("error calculating duration: %v", err)
	}

	for i := 0; i < len(agg); i++ {
		a := agg[i]
		fmt.Printf("%s: %.2f hours\n", a.Group, a.TotalHours)
	}
}

func calculateDuration(records []Record, period string) ([]AggregatedRecord, error) {
	if len(records) == 0 {
		return nil, errors.New("no records to process")
	}

	inferLastOut(&records)

	var aggregations map[string]AggregatedRecord
	var labeler func(time.Time) string

	switch period {
	case "daily":
		labeler = func(t time.Time) string {
			return t.Format("2006-01-02")
		}
	case "weekly":
		labeler = func(t time.Time) string {
			year, week := t.ISOWeek()
			return fmt.Sprintf("%d-W%02d", year, week)
		}
	case "monthly":
		labeler = func(t time.Time) string {
			return t.Format("2006-01")
		}
	case "yearly":
		labeler = func(t time.Time) string {
			return t.Format("2006")
		}
	default:
		return nil, fmt.Errorf("unsupported period: %s", period)
	}

	aggregations = aggregateBy(records, labeler)
	var out []AggregatedRecord
	for _, v := range aggregations {
		v.AverageHours = v.TotalHours / float64(len(v.Dates))
		out = append(out, v)
	}
	return out, nil
}

func aggregateBy(records []Record, groupFunc func(time.Time) string) map[string]AggregatedRecord {
	aggregations := make(map[string]AggregatedRecord)

	var lastOutTime time.Time
	for _, record := range records {
		if record.Kind == "out" {
			lastOutTime = record.Timestamp
		} else if record.Kind == "in" && !lastOutTime.IsZero() {
			groupKey := groupFunc(record.Timestamp)
			duration := lastOutTime.Sub(record.Timestamp).Hours()

			if agg, exists := aggregations[groupKey]; exists {
				agg.TotalHours += duration
				agg.Dates = append(agg.Dates, record.Timestamp.Format(printDateFormat))
				agg.Notes = append(agg.Notes, record.Notes)
				aggregations[groupKey] = agg
			} else {
				aggregations[groupKey] = AggregatedRecord{
					Group:      groupKey,
					TotalHours: duration,
					Dates:      []string{record.Timestamp.Format(printDateFormat)},
					Notes:      []string{record.Notes},
				}
			}
			lastOutTime = time.Time{} // reset
		}
	}

	return aggregations
}

func inferLastOut(records *[]Record) int {
	if len(*records) > 0 && (*records)[0].Kind == "in" {
		record := []Record{
			{
				Timestamp: time.Now(),
				Kind:      "out",
				Notes:     "Inferred by takt.",
			},
		}
		*records = append(record, *records...)
		return 1
	}
	return 0
}

func printRecords(records []Record) {
	fmt.Printf("%-25s %-5s %s\n", header[0], header[1], header[2])
	for _, record := range records {
		fmt.Printf("%-25s %-5s %s\n", record.Timestamp.Format(timeFormat), record.Kind, record.Notes)
	}
}

func createFile() {
	file, err := os.Create(fileName)
	if err != nil {
		fmt.Println("Error:", err)
		return
	}
	defer file.Close()

	writer := csv.NewWriter(file)
	defer writer.Flush()
	if err := writer.Write(header); err != nil {
		fmt.Println("Error:", err)
	}
}

func readRecords(nrows int) ([]Record, error) {
	return readRecordsFromFile(fileName, nrows)
}

// readRecords reads nrows records from the file
// if nrows is -1, read all records.
// skip the header.
func readRecordsFromFile(fileName string, head int) ([]Record, error) {
	if _, err := os.Stat(fileName); os.IsNotExist(err) {
		createFile()
	}
	file, err := os.Open(fileName)
	if err != nil {
		return nil, fmt.Errorf("could not open file: %w", err)
	}
	defer file.Close()
	reader := csv.NewReader(file)

	lines := [][]string{}
	linesRead := -1

	if head == -1 {
		// read all
		lines, err = reader.ReadAll()
		if err != nil {
			return nil, fmt.Errorf("could not read CSV: %w", err)
		}
	} else {
		// read n first nrows
		for i := 0; i < (head + 1); i++ {
			line, err := reader.Read()
			lines = append(lines, line)
			if err != nil {
				linesRead = i - 1 // avoid the header
				break
			}
		}
	}

	var records []Record
	if head == 0 || linesRead == 0 || len(lines) < 2 {
		return records, nil
	}
	for _, line := range lines[1:] {
		timestamp, _ := time.Parse(timeFormat, line[0])
		records = append(records, Record{timestamp, line[1], line[2]})
	}

	return records, nil
}

func checkAction(filename, notes string) {
	records, err := readRecordsFromFile(filename, 1)
	if err != nil {
		fmt.Println("Error:", err)
		return
	}

	var kind string
	if len(records) == 0 || records[0].Kind == "out" {
		kind = "in"
	} else {
		kind = "out"
	}

	timestamp := time.Now().Format(timeFormat)
	line := fmt.Sprintf("%s,%s,%s", timestamp, kind, notes)
	if err := writeRecords(filename, line); err != nil {
		fmt.Println("Error:", err)
	}

	fmt.Printf("Check %s at %s\n", kind, timestamp)
}

func writeRecords(fileName, newLine string) error {
	prevFile, err := os.Open(fileName)
	if err != nil {
		return err
	}
	defer prevFile.Close()

	newFile, err := os.CreateTemp("", "takt_tempfile.csv")
	if err != nil {
		fmt.Printf("Error: could not create temp file")
		return err
	}
	defer newFile.Close()

	newWriter := bufio.NewWriter(newFile)
	defer newWriter.Flush()
	_, err = newWriter.WriteString(fmt.Sprintf("%s,%s,%s\n", header[0], header[1], header[2]))
	if err != nil {
		fmt.Printf("Error: could not write to temp file")
		return err
	}
	_, err = newWriter.WriteString(newLine + "\n")
	if err != nil {
		fmt.Printf("Error: could not write to temp file")
		return err
	}

	prevReader := bufio.NewReader(prevFile)

	// drop the header
	_, _, err = prevReader.ReadLine()
	if err != nil {
		return err
	}
	_, err = io.Copy(newWriter, prevReader)
	if err != nil {
		return err
	}

	if err := os.Rename(newFile.Name(), fileName); err != nil {
		return err
	}

	return nil
}

func init() {
	rootCmd.AddCommand(checkCmd)
	rootCmd.AddCommand(editCmd)
	rootCmd.AddCommand(catCmd)
	rootCmd.AddCommand(dailyCmd)
	rootCmd.AddCommand(weekCmd)
	rootCmd.AddCommand(monthCmd)
	rootCmd.AddCommand(yearCmd)
}

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
}

func main() {
	Execute()
}
