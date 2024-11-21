# setup a basic cli

## Layout looks like this
```
cli-project/
├── cli/
│   └── __init__.py
│   └── main.py   <-- modules
├── setup.py
```

## Create Project Directory.
```sh
mkdir cli-project
cd cli-project
touch setup.py
mkdir cli
touch cli/__init__.py
touch cli/main.py
```

## Setup Virtual Environment stuff
```sh
python3 -m venv .venv
source .venv/bin/activate
```

## install and run
```bash
pip install -e .
pip freeze > requirements.txt
cli zac
```

### Magic setup.py stuff

```python
from setuptools import setup, find_packages

setup(
    name = 'cli',
    version = '0.1.0',
    packages = find_packages(),
    entry_points = {
        'console_scripts': [
            'cli = cli.main:main'
        ]
    },
)
```

## Parse some args
```python
import argparse

def main():
    # prep parser
    parser = argparse.ArgumentParser(description='Hello world CLI')
    parser.add_argument('name', type=str, help='To whom am I speaking?')
    args = parser.parse_args()

    # do something
    print(f'Hello, {args.name}!')

if __name__ == '__main__':
    main()
```