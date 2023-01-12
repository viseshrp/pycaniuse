DATE = $(shell date +'%Y%m%d')

build:
	python -m build --wheel
	rm -rf build

install:
	pip uninstall pycaniuse -y
	pip install dist/*.whl

install-dev:
	pip uninstall pycaniuse -y
	pip install -e .
	pip install -r requirements-dev.txt

smoketest:
	caniuse --help
	caniuse --version

clean:
	rm -rf dist build
	rm -rf *.egg-info
	find . -name \*.pyc -delete