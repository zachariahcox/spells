import errno
import os
import atexit

def cleanup(pipe_name):
    """Cleanup function to remove the named pipe on exit."""
    try:
        if os.path.exists(pipe_name):
            print(f"Cleaning up pipe: {pipe_name}")
            os.remove(pipe_name)
    except OSError as e:
        if e.errno != errno.ENOENT:  # Ignore if the pipe does not exist
            raise

def handle_message(message):
    if message == "exit":
        print("Received exit command. Shutting down server.")
        exit(0)

    print("Received message:", message)

if __name__ == '__main__':
    # parse command line args to get the pipe name
    # but for this example, we will use a fixed pipe name
    pipe_name = "its_a_pipe"
    cleanup(pipe_name)  # Ensure cleanup on start

    # register cleanup function to remove the pipe file on exit
    atexit.register(cleanup, pipe_name)

    # Create a named pipe (FIFO) if it does not exist
    try:
        os.mkfifo(pipe_name)
    except OSError as oe:
        if oe.errno != errno.EEXIST:
            raise

    # Continuously read from the named pipe
    print(f"Server is listening on {pipe_name}...")
    while True:
        with open(pipe_name) as fifo:
            data = fifo.read()

            handle_message(data)
