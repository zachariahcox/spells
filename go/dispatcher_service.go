// dispatcher / worker pattern for unknown amounts of work

package main

import (
	"fmt"
	"sync"
)

type Job struct {
	Id        int
	Completed bool
}

func (j *Job) DoIt() {
	fmt.Println("completed job", j.Id)
	j.Completed = true
}

type Result struct {
	Job *Job
}

type Worker struct {
	WorkerPool chan chan Job
	JobChannel chan Job
	quit       chan bool
}

func NewWorker(workerPool chan chan Job) *Worker {
	return &Worker{
		WorkerPool: workerPool,
		JobChannel: make(chan Job),
		quit:       make(chan bool),
	}
}

// A worker will wait for work then do it.
// It will do this until it receives the quit signal.
func (w *Worker) Start() {
	// the goroutine is launched from inside this function
	go func() {
		for {
			// register the current worker into the worker queue.
			w.WorkerPool <- w.JobChannel

			// wait for either a job or a quit signal
			select {
			case job := <-w.JobChannel:
				// we have received a job to do
				job.DoIt()

			case <-w.quit:
				// we have received a signal to stop
				return
			}
		}
	}()
}

// Send the quit signal to the worker.
func (w *Worker) Stop() {
	go func() {
		w.quit <- true // send a "true" to the quit channel over in the running goroutine
	}()
}

// A buffered channel that we can send work requests on.
var JobQueue chan Job

type Dispatcher struct {
	// this is a channel of each worker's job channel
	WorkerPool chan chan Job
}

func NewDispatcher(maxWorkers int) *Dispatcher {

	pool := make(chan chan Job, maxWorkers)
	return &Dispatcher{WorkerPool: pool}
}

func (d *Dispatcher) dispatch() {
	for {
		select {
		case job := <-JobQueue:
			// a job request has been received
			go func(job Job) {
				// try to obtain a worker job channel that is available.
				// this will block until a worker is idle
				jobChannel := <-d.WorkerPool

				// dispatch the job to the worker job channel
				jobChannel <- job
			}(job)
		}
	}
}

func (d *Dispatcher) Run() {
	for i := 0; i < cap(d.WorkerPool); i++ {
		worker := NewWorker(d.WorkerPool)
		worker.Start()
	}

	go d.dispatch()
}

func DistributeABunchOfWork_OneShot(jobs []*Job, workerCount int) []*Result {
	jobCount := len(jobs)
	jobQueue := make(chan *Job, jobCount)
	results := make(chan *Result, jobCount)

	// Start workers
	var wg sync.WaitGroup
	wg.Add(workerCount)
	for w := 1; w <= workerCount; w++ {
		go func() {
			defer wg.Done() // each worker gets one list of jobs?
			for job := range jobQueue {
				job.DoIt()
				results <- &Result{Job: job}
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

func main() {

	// create pile of work to do
	jobs := make([]*Job, 0, 100)
	for i := 1; i <= 100; i++ {
		jobs = append(jobs, &Job{Id: i})
	}

	// create a dispatcher and start it
	results := DistributeABunchOfWork_OneShot(jobs, 10)
	fmt.Println("processed", len(jobs), "jobs and received", len(results), "results")
}
