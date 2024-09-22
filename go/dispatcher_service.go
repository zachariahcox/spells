// dispatcher / worker pattern for unknown amounts of work

package main

type Job struct {
	Id          int
	CompletedBy int
}

func (j *Job) DoIt(workerId int) {
	j.CompletedBy = workerId
}

type Result struct {
	Job *Job
}

type Worker struct {
	Id         int
	WorkerPool chan chan *Job
	JobChannel chan *Job
	quit       chan bool
}

func NewWorker(id int, workerPool chan chan *Job) *Worker {
	return &Worker{
		Id:         id,
		WorkerPool: workerPool,
		JobChannel: make(chan *Job),
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
				job.DoIt(w.Id)

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

type Dispatcher struct {
	// this is a channel of each worker's job channel
	WorkerPool chan chan *Job
	JobQueue   <-chan *Job
}

func NewDispatcher(jobQueue <-chan *Job, maxWorkers int) *Dispatcher {
	pool := make(chan chan *Job, maxWorkers)
	return &Dispatcher{WorkerPool: pool, JobQueue: jobQueue}
}

func (d *Dispatcher) dispatch() {
	for {
		select {
		case job := <-d.JobQueue:
			// a job request has been received
			go func(job *Job) {
				// try to obtain a worker job channel that is available.
				// (this will block until a worker is idle)
				jobChannel := <-d.WorkerPool

				// dispatch the job to the worker job channel
				jobChannel <- job
			}(job)
		}
	}
}

func (d *Dispatcher) Run() {
	for i := 0; i < cap(d.WorkerPool); i++ {
		worker := NewWorker(i, d.WorkerPool)
		worker.Start()
	}
	go d.dispatch()
}

func main() {
	numberOfJobs := 1000
	numberOfWorkers := 10
	jobQueue := make(chan *Job)

	// create a dispatcher and start it
	dispatcher := NewDispatcher(jobQueue, numberOfWorkers)
	dispatcher.Run()

	// create pile of work to do
	for i := 0; i < numberOfJobs; i++ {
		jobQueue <- &Job{Id: i}
	}
	close(jobQueue) // close the channel to signal that there are no more jobs

	// fmt.Println("processed", numberOfJobs, "jobs and received", len(results), "results")

	// how evenly were the jobs distributed?
	// counts := make([]int, numberOfWorkers)
	// for _, r := range results {
	// 	counts[r.ProcessedByWorkerId] += 1
	// }
	// sort.Slice(counts, func(i, j int) bool {
	// 	return counts[i] > counts[j]
	// })
	// for id, count := range counts {
	// 	fmt.Println("worker", id, "processed", count, "jobs")
	// }
}
