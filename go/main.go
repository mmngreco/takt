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
	"time"

	"github.com/spf13/cobra"
)

const fileName = "csvfile.csv"

// const timeFormat = time.RFC3339
const timeFormat = "2006-01-02T15:04:05"
const outDateFormat = "2006-01-02"

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
		checkAction(notes)
	},
}

var displayCmd = &cobra.Command{
	Use:     "display",
	Aliases: []string{"d"},
	Short:   "Show all records",
	Run: func(cmd *cobra.Command, args []string) {
		// TODO: add flags to specify the number of records to display
		records, err := readRecords(-1)
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

var summaryCmd = &cobra.Command{
	Use:     "summary",
	Aliases: []string{"s"},
	Short:   "Daily summary",
	Run: func(cmd *cobra.Command, args []string) {
		println("summary")
		records, err := readRecords(-1)
		if err != nil {
			log.Fatal(err)
		}
		agg, err := calculateDuration(records, "daily")

		for i := 0; i < len(agg); i++ {
			a := agg[i]
			fmt.Printf("%s: %.2f hours\n", a.Group, a.TotalHours)
		}
	},
}

var wtdCmd = &cobra.Command{
	Use:     "wtd",
	Aliases: []string{"w"},
	Short:   "Week to date summary",
	Run: func(cmd *cobra.Command, args []string) {
		println("wtd")
	},
}

var mtdCmd = &cobra.Command{
	Use:     "mtd",
	Aliases: []string{"m"},
	Short:   "Month to date summary",
	Run: func(cmd *cobra.Command, args []string) {
		println("mtd")
	},
}

var ytdCmd = &cobra.Command{
	Use:     "ytd",
	Aliases: []string{"y"},
	Short:   "Year to date summary",
	Run: func(cmd *cobra.Command, args []string) {
		println("ytd")
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
		fmt.Printf("%+v\n", v)
		v.AverageHours = v.TotalHours / float64(len(v.Dates))
		out = append(out, v)
	}
	return out, nil
}

func aggregateBy(records []Record, groupFunc func(time.Time) string) map[string]AggregatedRecord {
	aggregations := make(map[string]AggregatedRecord)

	var lastOutTime time.Time
	for _, record := range records {
		fmt.Printf("=== %+v\n", record)
		if record.Kind == "out" {
			fmt.Println("out")
			lastOutTime = record.Timestamp
		} else if record.Kind == "in" && !lastOutTime.IsZero() {
			groupKey := groupFunc(record.Timestamp)
			// lastOutTime - lastInTime
			fmt.Printf("lastOutTime: %+v\n", lastOutTime)
			fmt.Printf("lastInTime: %+v\n", record.Timestamp)
			duration := lastOutTime.Sub(record.Timestamp).Hours()
			fmt.Printf("duration: %f\n", duration)

			if agg, exists := aggregations[groupKey]; exists {
				agg.TotalHours += duration
				agg.Dates = append(agg.Dates, record.Timestamp.Format(outDateFormat))
				agg.Notes = append(agg.Notes, record.Notes)
				aggregations[groupKey] = agg
			} else {
				aggregations[groupKey] = AggregatedRecord{
					Group:      groupKey,
					TotalHours: duration,
					Dates:      []string{record.Timestamp.Format(outDateFormat)},
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
				Timestamp: time.Now().UTC(),
				Kind:      "out",
				Notes:     "Inferred by takt.",
			},
		}
		*records = append(record, *records...)
		fmt.Println("Inferred last out.")
		fmt.Printf("%+v\n", record)
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

// readRecords reads nrows records from the file
// if nrows is -1, read all records.
// skip the header.
func readRecords(nrows int) ([]Record, error) {
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

	if nrows == -1 {
		// read all
		lines, err = reader.ReadAll()
		if err != nil {
			return nil, fmt.Errorf("could not read CSV: %w", err)
		}
	} else {
		// read first nrows
		for i := 0; i < (nrows + 1); i++ {
			line, err := reader.Read()
			lines = append(lines, line)
			if err != nil {
				return nil, fmt.Errorf("could not read CSV: %w", err)
			}
		}
	}

	var records []Record
	if nrows == 0 || len(lines) < 2 {
		return records, nil
	}
	for _, line := range lines[1:] {
		timestamp, _ := time.Parse(timeFormat, line[0])
		records = append(records, Record{timestamp, line[1], line[2]})
	}

	return records, nil
}

func checkAction(notes string) {
	records, err := readRecords(1)
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
	if err := writeRecords(fileName, line); err != nil {
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
		return err
	}
	defer newFile.Close()

	newWriter := bufio.NewWriter(newFile)
	defer newWriter.Flush()
	_, err = newWriter.WriteString(fmt.Sprintf("%s,%s,%s\n", header[0], header[1], header[2]))
	_, err = newWriter.WriteString(newLine + "\n")
	if err != nil {
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

	newWriter.Flush()

	if err := os.Rename(newFile.Name(), fileName); err != nil {
		return err
	}

	return nil
}

func init() {
	rootCmd.AddCommand(checkCmd)
	rootCmd.AddCommand(editCmd)
	rootCmd.AddCommand(displayCmd)
	rootCmd.AddCommand(summaryCmd)
	rootCmd.AddCommand(wtdCmd)
	rootCmd.AddCommand(mtdCmd)
	rootCmd.AddCommand(ytdCmd)
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
