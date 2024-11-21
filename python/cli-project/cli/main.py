import argparse

def main():
    # setup the parser
    parser = argparse.ArgumentParser(description='Demo CLI tool')
    parser.add_argument('name', type=str, help='Name to greet')
    args = parser.parse_args()

    # print the greeting
    print(f'Hello, {args.name}!')


# check if this is the file is executed by name vs included in a module.
if __name__ == "__main__":
    main()