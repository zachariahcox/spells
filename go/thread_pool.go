package main

type Job struct {
	Payload string
}

func (*Job) DoIt() {
	print("completed job", job.Payload)
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
	WorkerPool chan chan Job // this is a channel on which to receive a channel of jobs
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

func main() {
	d := NewDispatcher(5)
	d.Run()

	JobQueue = make(chan Job)

}
