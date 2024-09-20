import (
	"fmt"
)

type Job struct {
	Payload string
}

func (*job) DoIt() {
	print("completed job", job.Payload)
}

type Worker struct {
	WorkerPool chan chan Job
	JobChannel chan Job
	quit       chan bool
}

func NewWorker(workerPool chan chan Job) *Worker {
	return Worker{
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
	WorkerPool chan chan Job // this is a channel on which to receive a channel of jobs
}

func NewDispatcher(maxWorkers int) *Dispatcher {
	pool := make(chan chan Job, maxWorkers)
	return &Dispatcher{WorkerPool: pool}
}

func (d *Dispatcher) Run() {
	// starting n number of workers
	for i := 0; i < d.maxWorkers; i++ {
		worker := NewWorker(d.pool)
		worker.Start()
	}

	go d.dispatch()
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

func main() {
	// // make a work-passing channel
	// workChannel := make(chan string)

	// // make a workgroup to prevent this function from returning
	// //  until all the goroutines are done
	// wg := new(sync.WaitGroup)

	// // how many goroutines to run at once?
	// // goroutines are much cheaper than threads -- many can run on the same OS thread.
	// // golang uses dynamic stack sizes but they are small -- maybe 4k per stack.
	// //   you can then put 1M goroutines on a machine with 4GB of memory.
	// numberOfGoRoutines := 250

	// // Adding routines to workgroup and running then
	// for i := 0; i < numberOfGoRoutines; i++ {
	// 	wg.Add(1)
	// 	go worker(workChannel, wg)
	// }

	// // Processing all links by spreading them to `free` goroutines
	// for _, link := range yourLinksSlice {
	// 	workChannel <- link
	// }

	// // wait for all the goroutines to finish
	// close(workChannel)
	// wg.Wait()
}