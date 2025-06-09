import os
import sys

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python client.py <message>")
        sys.exit(1)

    # parse command line args to get the pipe name
    pipe_name = sys.argv[1]

    # Check if the named pipe exists
    if not os.path.exists(pipe_name):
        print(f"Error: Named pipe '{pipe_name}' does not exist. Please ensure the server is running and the pipe is created.")
        sys.exit(1)

    message = ' '.join(sys.argv[2:]) if len(sys.argv) > 2 else "Hello, Server!"
    
    # Open the named pipe for writing
    fifo = os.open(pipe_name, os.O_WRONLY)
    try:
        os.write(fifo, message.encode())
    except OSError as e:
        print(f"Error writing to pipe: {e}")
        sys.exit(1)
    finally:
        os.close(fifo)