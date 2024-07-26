package main

import (
	"bufio"
	"encoding/csv"
	"errors"
	"fmt"
	"io"
	"log"
	"math"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"time"

	"github.com/spf13/cobra"
)

var Version = "2024.07.4"
var fileName = getFileName("TAKT_FILE", "csvfile.csv")
var header = []string{"timestamp", "kind", "notes"}

const timeFormat = time.RFC3339
const printDateFormat = "2006-01-02"

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

func absPath(path string) (string, error) {
	if path[:2] == "~/" {
		home, err := os.UserHomeDir()
		if err != nil {
			fmt.Println("Error: could not get user home directory")
			return "", err
		}
		return filepath.Join(home, path[2:]), nil
	}
	return path, nil
}

func getFileName(key, dflt string) string {
	path := os.Getenv(key)

	if path == "" {
		out, err := absPath(dflt)
		if err != nil {
			return ""
		}
		return out
	}

	out, err := absPath(path)
	if err != nil {
		return ""
	}
	return out

}
func sortedKeys(m map[string]AggregatedRecord) []string {
	// Crear un slice para las claves
	keys := make([]string, 0, len(m))

	// Agregar las claves al slice
	for k := range m {
		keys = append(keys, k)
	}

	// Ordenar las claves
	sort.Strings(keys)

	// invert the order
	out := make([]string, 0, len(keys))
	for i := len(keys) - 1; i >= 0; i-- {
		out = append(out, keys[i])
	}

	return out
}

func hoursToText(totalHours float64) string {

	if totalHours <= 0 {
		return "00h00m"
	} else if totalHours <= 24 {
		hours := int(totalHours)
		minutes := int(math.Round((float64(totalHours) - float64(hours)) * 60))
		return fmt.Sprintf("%dh%02dm", hours, minutes)
	} else {
		days := int(totalHours / 24)
		hours := int(totalHours) % 24
		minutes := int(math.Round((float64(totalHours) - float64(days*24+hours)) * 60))
		return fmt.Sprintf("%dd%02dh%02dm", days, hours, minutes)
	}
}

func summary(offset string, head int) {
	records, err := readRecords(-1)
	if err != nil {
		log.Fatal(err)
	}
	agg, err := calculateDuration(records, offset)
	if err != nil {
		log.Fatalf("error calculating duration: %v", err)
	}

	if head < 1 || head > len(agg) {
		head = len(agg)
	}

	var outFmt string
	if offset == "day" {
		outFmt = "%-8s %6s\t%4s\t%6s\n"
	} else {
		// wider total hours column for week, month, year
		outFmt = "%-8s %10s\t%4s\t%6s\n"
	}

	fmt.Printf(outFmt, "Date", "Total", "Days", "Avg")
	for i := 0; i < head; i++ {
		a := agg[i]
		hhmm := hoursToText(a.TotalHours)
		ndays := strconv.Itoa(len(a.Dates))
		avg := hoursToText(a.AverageHours)
		fmt.Printf(outFmt, a.Group, hhmm, ndays, avg)
	}
}

func contains(items []string, item string) bool {
	for _, it := range items {
		if it == item {
			return true
		}
	}
	return false
}

func unique(items []string) []string {

	out := []string{}
	for _, it := range items {
		if !contains(out, it) {
			out = append(out, it)
		}
	}
	return out
}

func calculateDuration(records []Record, period string) ([]AggregatedRecord, error) {
	if len(records) == 0 {
		return nil, errors.New("no records to process")
	}

	inferLastOut(&records)

	var aggregations map[string]AggregatedRecord
	var labeler func(time.Time) string

	switch period {
	case "day":
		labeler = func(t time.Time) string {
			return t.Format("2006-01-02")
		}
	case "week":
		labeler = func(t time.Time) string {
			year, week := t.ISOWeek()
			return fmt.Sprintf("%d-W%02d", year, week)
		}
	case "month":
		labeler = func(t time.Time) string {
			return t.Format("2006-01")
		}
	case "year":
		labeler = func(t time.Time) string {
			return t.Format("2006")
		}
	default:
		return nil, fmt.Errorf("unsupported period: %s", period)
	}

	aggregations = aggregateBy(records, labeler)
	var out []AggregatedRecord
	keys := sortedKeys(aggregations)
	for _, k := range keys {
		v := aggregations[k]
		v.Dates = unique(v.Dates)
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

func readRecords(head int) ([]Record, error) {
	return readRecordsFromFile(fileName, head)
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
				// NOTE: i can happen that the head is greater
				// thant the number of lines in the file.
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

var rootCmd = &cobra.Command{
	Use:   "takt [COMMAND] [ARGS]",
	Short: "CLI Time Tracking Tool",
	Long:  "This is a simple time tracking tool that allows you to check in and out.",
}

var checkCmd = &cobra.Command{
	Aliases: []string{"c"},
	Use:     "check [NOTE]",
	Short:   "Check in or out",
	Long:    "Check in or out. If NOTE is provided, it will be saved with the record.",
	Run: func(cmd *cobra.Command, args []string) {
		notes := ""
		if len(args) > 0 {
			notes = args[0]
		}
		checkAction(fileName, notes)
	},
}

var catCmd = &cobra.Command{
	Aliases: []string{"display"},
	Use:     "cat [HEAD]",
	Short:   "Show all records",
	Long:    "Show all records. If HEAD is provided, show the first n records.",
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

var dayCmd = &cobra.Command{
	Aliases: []string{"d"},
	Use:     "day [HEAD]",
	Short:   "Daily summary",
	Long:    "Daily summary. If HEAD is provided, show the first n records.",
	Run: func(cmd *cobra.Command, args []string) {
		head := -1 // read all records
		var err error
		if len(args) > 0 {
			head, err = strconv.Atoi(args[0])
			if err != nil {
				log.Fatal(err)
			}
		}
		summary("day", head)
	},
}

var weekCmd = &cobra.Command{
	Aliases: []string{"w"},
	Use:     "week [HEAD]",
	Short:   "Week to date summary",
	Long:    "Week to date summary. If HEAD is provided, show the first n records.",
	Run: func(cmd *cobra.Command, args []string) {
		head := -1 // read all records
		var err error
		if len(args) > 0 {
			head, err = strconv.Atoi(args[0])
			if err != nil {
				log.Fatal(err)
			}
		}
		summary("week", head)
	},
}

var monthCmd = &cobra.Command{
	Aliases: []string{"m"},
	Use:     "month [HEAD]",
	Short:   "Month to date summary",
	Long:    "Month to date summary. If HEAD is provided, show the first n records.",
	Run: func(cmd *cobra.Command, args []string) {
		head := -1 // read all records
		var err error
		if len(args) > 0 {
			head, err = strconv.Atoi(args[0])
			if err != nil {
				log.Fatal(err)
			}
		}
		summary("month", head)
	},
}

var yearCmd = &cobra.Command{
	Aliases: []string{"y"},
	Use:     "year [HEAD]",
	Short:   "Year to date summary",
	Long:    "Year to date summary. If HEAD is provided, show the first n records.",
	Run: func(cmd *cobra.Command, args []string) {
		head := -1 // read all records
		var err error
		if len(args) > 0 {
			head, err = strconv.Atoi(args[0])
			if err != nil {
				log.Fatal(err)
			}
		}
		summary("year", head)
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

var versionCmd = &cobra.Command{
	Use:   "version",
	Short: "Print the version number of takt",
	Long:  "Print the version number of takt and exit.",
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Println("Version:", Version)
	},
}

func init() {
	rootCmd.AddCommand(checkCmd)
	rootCmd.AddCommand(catCmd)
	rootCmd.AddCommand(dayCmd)
	rootCmd.AddCommand(weekCmd)
	rootCmd.AddCommand(monthCmd)
	rootCmd.AddCommand(yearCmd)
	rootCmd.AddCommand(editCmd)
	rootCmd.AddCommand(versionCmd)
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
