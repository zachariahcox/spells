package main

import (
	"fmt"
	"math"
	"os"
	"strings"
	"time"
)

func load_file(path string, delimiter string) []string {
	contents, err := os.ReadFile(path) // automatically closes it
	if err != nil {
		fmt.Println("File reading error", err)
		return nil
	}
	return strings.Split(strings.ToLower(string(contents)), delimiter)
}

func is_real_word(all_words []string, s string) bool {
	// the word is real if it exists in the list!
	for _, value := range all_words {
		if s == value {
			return true
		}
	}
	return false
}

func main() {
	// load words from data set
	start_time := time.Now()
	all_words := load_file("words.txt", "\n")
	end_time := time.Now()
	fmt.Println("loaded", len(all_words), "words in", int(end_time.UnixMilli())-int(start_time.UnixMilli()), "ms")

	// generate new words
	my_words := []string{
		"fizz",
		"buzz"}
	my_words_count := len(my_words)
	new_words := make([]string, int(math.Pow(float64(my_words_count), 2)))
	for i, first_word := range my_words {
		first_letter := first_word[:1]
		for j, second_word := range my_words {
			array_index := i*my_words_count + j
			new_words[array_index] = first_letter + second_word[1:]
		}
	}

	for _, value := range new_words {
		if is_real_word(all_words, value) {
			fmt.Println(value, "IS a real word!")
		} else {
			fmt.Println(value, "is NOT a real word.")
		}
	}
}
