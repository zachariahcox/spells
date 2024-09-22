// dispatcher / worker pattern for unknown amounts of work

package main

import (
	"fmt"
	"sort"
	"sync"
	"time"
)

type Job struct {
	Id int
}

func (j *Job) DoIt(workerId int) {
	fmt.Println("job #", j.Id, "completed by worker #", workerId)
}

type Result struct {
	Job                 *Job
	ProcessedByWorkerId int
}

func DistributeJobs(jobs []*Job, workerCount int) []*Result {
	jobCount := len(jobs)
	jobQueue := make(chan *Job, jobCount)
	results := make(chan *Result, jobCount)

	// Start workers
	var wg sync.WaitGroup
	wg.Add(workerCount)
	for w := 0; w < workerCount; w++ {
		go func() {
			defer wg.Done() // each worker gets one list of jobs?
			for job := range jobQueue {
				job.DoIt(w)
				results <- &Result{Job: job, ProcessedByWorkerId: w}
			}
		}()
	}

	// Start results collector
	var resultsWg sync.WaitGroup
	finishedWorkChannel := make(chan []*Result, 1)
	resultsWg.Add(1)
	go func() {
		defer resultsWg.Done()
		rc := make([]*Result, 0, jobCount)
		for result := range results {
			fmt.Println("result for job", result.Job.Id)
			rc = append(rc, result)
		}
		finishedWorkChannel <- rc // "return" values are passed via channel
	}()

	// Distribute jobs and wait for completion
	// there is no better way in golang to add all things to a channel
	for _, job := range jobs {
		jobQueue <- job
	}
	close(jobQueue)  // close the channel to signal that there are no more jobs
	wg.Wait()        // wait for all workers to finish
	close(results)   // the workers are done, so close the results channel to signal that there are no more results
	resultsWg.Wait() // wait for the results to be collected

	return <-finishedWorkChannel
}

// run with `go run dispatcher_blast.go`
func main() {

	numberOfWorkers := 10
	numberOfJobs := 1000

	// create pile of work to do
	jobs := make([]*Job, 0, numberOfJobs)
	for i, c := 0, cap(jobs); i < c; i++ {
		jobs = append(jobs, &Job{Id: i})
	}

	// create a dispatcher and start it
	startTime := time.Now()
	results := DistributeJobs(jobs, numberOfWorkers)
	elapsed := time.Since(startTime)

	fmt.Println("processed", len(jobs), "jobs and received", len(results), "results in", elapsed)

	// how evenly were the jobs distributed?
	counts := make([]int, numberOfWorkers)
	for _, r := range results {
		counts[r.ProcessedByWorkerId] += 1
	}
	sort.Slice(counts, func(i, j int) bool {
		return counts[i] > counts[j]
	})
	for id, count := range counts {
		fmt.Println("worker", id, "processed", count, "jobs")
	}
}
